#!/usr/bin/env python3
"""합성 학부모 민원 생성기 — F1 분류기 학습·평가용 라벨 데이터를 만든다.

## 왜 필요한가

F1(민원 자동 분류)을 자체 모델로 학습하려면 "이 민원은 성적 카테고리" 라벨이
붙은 데이터가 필요한데, 학교 민원 분류는 이 프로젝트 고유 과제라 공개 데이터가
없다. 그래서 로컬 LLM 으로 카테고리별 민원을 생성해 초기 라벨 데이터를 만든다.

용도 세 가지:
  1. F1 분류기 학습·평가 데이터의 출발점
  2. 테스트 픽스처 (특히 F3 오차단 회귀 — `--check-filter` 참고)
  3. 데모 시드 데이터

## 반드시 알아야 할 한계 — 분포 갭

LLM 이 만든 민원은 실제 학부모가 쓴 민원과 다르다. 더 정제되고, 오타·방언·
비문·감정 폭발이 적고, 문장 길이가 균일하다. **합성 평가셋에서 정확도 95% 가
나와도 실제 민원에서는 떨어진다.** 이 데이터는 어디까지나 출발점이고, 실제
민원이 쌓이는 대로 재학습·재평가해야 한다.

그래서 모든 레코드에 `source: "synthetic"` 을 박는다. 실제 데이터와 절대
섞이지 않게 하기 위한 것이니 지우지 말 것.

## 욕설·위협은 생성하지 않는다

F3 필터 픽스처는 `tests/test_content_filter.py` 에 손으로 큐레이션돼 있다.
욕설·협박 문장을 대량 생성하는 것은 얻는 것보다 잃는 것이 많고(모델이 거부하거나
품질이 낮고, 저장·공유 리스크가 생긴다), F2 위험 탐지 학습에는 한국어 혐오표현
공개 데이터셋(Unsmile, BEEP!, KOLD 등)을 쓰는 편이 낫다.
이 스크립트는 **정당한 민원**만 만들고, 위험도는 정중함~강한 불만 범위에서 조절한다.

## 실행

Ollama(기본) 또는 OpenAI 호환 엔드포인트가 필요하다. 의존성은 표준 라이브러리뿐이라
백엔드 venv 없이도 돌아간다.

    ollama serve                       # 별도 터미널
    python scripts/gen_synthetic_complaints.py --count 30 --model gemma3:4b

    # 생성물이 F3 필터에 오차단되는지 측정 (백엔드 의존성이 있을 때만)
    python scripts/gen_synthetic_complaints.py --count 30 --check-filter

출력은 JSONL. `--eval-ratio` 를 주면 본문 해시로 결정론적 분할을 해서
같은 데이터가 항상 같은 쪽(train/eval)에 가도록 한다(재실행 시 오염 방지).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# db/schema.sql 의 complaint_category · app/services/ai/classifier.CATEGORIES 와
# 일치해야 한다. tests/test_synthetic_gen.py 가 이 일치를 검사한다.
CATEGORIES = ["administrative", "learning", "life", "grades", "violence_dispute", "other"]

# 카테고리별 생성 지침. 실제 학교 민원에서 자주 나오는 소재를 준다.
CATEGORY_GUIDE = {
    "administrative": (
        "단순 행정 문의. 서류 발급, 제출 기한, 급식·식단, 준비물, 방과후 신청, "
        "현장학습 동의서, 증명서, 결석 신고, 교복·물품 지원 같은 소재."
    ),
    "learning": (
        "학습 지도에 관한 문의. 수업 진도, 숙제 양, 과제 방식, 교재, 보충 학습, "
        "학습 부진 상담 같은 소재. 성적·점수 이야기는 넣지 말 것."
    ),
    "life": (
        "생활지도에 관한 문의. 지각·결석 습관, 복장·두발, 교우 관계, 수업 태도, "
        "등하교 안전, 휴대폰 사용 규칙 같은 소재. 폭력·괴롭힘은 넣지 말 것."
    ),
    "grades": (
        "성적·평가에 관한 문의. 수행평가 채점 기준, 점수 산정, 시험 범위, "
        "성적표 오류, 재평가 요청, 등급 산출 같은 소재."
    ),
    "violence_dispute": (
        "학교폭력·분쟁을 **신고하거나 상담을 요청하는** 민원. 괴롭힘, 따돌림, "
        "신체적 충돌, 금품 갈취, 사이버 괴롭힘, 학생 간 분쟁 같은 소재. "
        "학부모는 피해를 알리고 도움을 구하는 입장이며, 욕설이나 협박은 절대 쓰지 않는다."
    ),
    "other": (
        "위 다섯 가지에 들어가지 않는 문의. 학교 시설(난방·전등·화장실), 통학버스, "
        "교내 행사, 학부모회, 방역·위생, 분실물 같은 소재."
    ),
}

# 카테고리별로 본문에 최소 하나는 있어야 하는 신호.
#
# 라벨이 프롬프트에서 오기 때문에, 모델이 주제를 벗어나면 **잘못된 라벨이 그대로
# 데이터가 된다.** 실제로 gemma3:4b 가 violence_dispute 프롬프트에 "학습 부진 상담"
# 을 만들어낸 적이 있다. 그걸로 학습하면 분류기가 '학습 부진 = 학교폭력'을 배운다.
# 신호가 없으면 버린다 — 애매한 표본을 남기는 것보다 수량이 줄는 게 낫다.
# `other` 는 포괄 카테고리라 신호를 요구하지 않는다.
REQUIRED_SIGNALS = {
    "administrative": ["서류", "신청", "기한", "급식", "식단", "준비물", "증명서", "동의서",
                       "발급", "제출", "안내", "방과후", "현장학습", "결석", "교복", "지원금",
                       "일정", "등록", "납부"],
    "learning": ["수업", "학습", "숙제", "과제", "진도", "교재", "보충", "예습", "복습",
                 "공부", "학업", "지도"],
    "life": ["생활", "지각", "복장", "두발", "친구", "교우", "태도", "등교", "하교",
             "휴대폰", "규칙", "습관", "안전"],
    "grades": ["성적", "점수", "평가", "시험", "채점", "등급", "성적표", "재평가", "산정"],
    "violence_dispute": ["폭력", "폭행", "괴롭", "따돌", "왕따", "학폭", "때리", "때려",
                         "때렸", "맞았", "싸움", "다툼", "갈취", "협박", "위협", "밀치",
                         "분쟁", "사이버", "험담", "욕설"],
    "other": [],
}

# 같은 문장이 반복되지 않도록 프롬프트를 흔드는 축.
GRADES = ["초등학교 1학년", "초등학교 3학년", "초등학교 5학년", "초등학교 6학년",
          "중학교 1학년", "중학교 2학년", "중학교 3학년"]
SPEAKERS = ["어머니", "아버지", "할머니", "보호자"]
TONES = [
    ("정중하고 차분한", "low"),
    ("사무적이고 간결한", "low"),
    ("걱정이 묻어나는", "low"),
    ("아쉬움을 표현하는", "medium"),
    ("불만이 분명한", "medium"),
    ("여러 번 문의했다며 답답함을 드러내는", "high"),
]
LENGTHS = ["한두 문장으로 짧게", "세네 문장으로", "다섯 문장 정도로 상세하게"]

SYSTEM_PROMPT = """너는 한국 학교에 실제로 접수되는 학부모 민원 예시를 만드는 데이터 생성기다.
규칙:
- 실제 학부모가 쓴 것처럼 자연스러운 한국어로 쓴다.
- 욕설, 협박, 인격 모독 표현은 절대 쓰지 않는다.
- 실존 인물·학교·지역 이름을 쓰지 않는다. 아이는 '아이', '저희 아이'로 지칭한다.
- 개인정보(전화번호, 주소, 주민번호)를 넣지 않는다.
- 매번 다른 상황과 다른 문장 구조를 쓴다. 앞의 예시를 베끼지 않는다.
- JSON 배열로만 답한다. 설명이나 코드블록 표시를 붙이지 않는다."""


def pick_tones(n: int, variety_index: int) -> list[tuple[str, str]]:
    """이 배치에서 쓸 어조를 순서대로 고른다. 스크립트가 순서를 알고 있으므로
    모델에게 어조 이름을 되돌려 받을 필요가 없다(본문 오염 방지)."""
    return [TONES[(variety_index + i) % len(TONES)] for i in range(n)]


def build_prompt(category: str, n: int, variety_index: int) -> str:
    """카테고리 + 변형 축을 조합한 사용자 프롬프트.

    설계상 주의 두 가지 — 둘 다 실제로 데이터를 오염시킨 적이 있다.
    1. 어조 이름을 모델이 되돌려 적게 하면 **본문 앞에도 붙여 쓴다**
       ("아쉬움을 표현하는 어조로, 저희 아이가..."). 그래서 어조는 항목별로
       지시만 하고 결과 필드로 받지 않는다. 위험도 힌트는 지시한 순서대로 붙인다.
    2. 필수 키워드 목록을 프롬프트에 넣으면 **인용부호로 감싸 억지로 박아넣는다**
       ("'괴롭히고 따돌'어"). 그래서 키워드는 프롬프트에 넣지 않고 생성 후
       검증(REQUIRED_SIGNALS)에만 쓴다. 프롬프트에서는 '구체적 사건 서술'을 요구한다.
    """
    grade = GRADES[variety_index % len(GRADES)]
    speaker = SPEAKERS[variety_index % len(SPEAKERS)]
    length = LENGTHS[variety_index % len(LENGTHS)]
    tones = pick_tones(n, variety_index)
    tone_lines = "\n".join(f"  {i + 1}번: {t}" for i, (t, _) in enumerate(tones))

    return f"""{grade} 학생의 {speaker}가 쓴 민원 {n}개를 만들어라.

[카테고리]
{CATEGORY_GUIDE[category]}

[가장 중요]
무슨 일이 있었는지 **구체적인 상황**을 서술하라. 언제, 어디서, 무엇이 문제인지가
드러나야 한다. 위 카테고리의 소재에서 벗어나 다른 주제로 넘어가면 안 된다.

[항목별 어조]
{tone_lines}

[분량]
본문은 {length} 쓴다.

[금지]
- 어조 이름이나 위 지시문을 본문에 쓰지 마라. 본문은 학부모가 쓴 민원 그 자체여야 한다.
- 특정 단어를 인용부호로 감싸 억지로 끼워넣지 마라. 자연스러운 문장으로 써라.

[출력 형식]
JSON 배열. 각 원소는 다음 키를 가진다.
- "title": 민원 제목 (15자 이내, 명사형)
- "body": 민원 본문

순서를 지켜 {n}개를 출력하고, 모두 서로 다른 상황이어야 한다. JSON 배열만 출력하라."""


# --- LLM 호출 ---------------------------------------------------------------

def call_llm(base_url: str, model: str, prompt: str, temperature: float, timeout: float) -> str:
    """OpenAI 호환 /chat/completions 호출. 실패하면 예외를 올린다(조용히 넘기지 않음)."""
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def extract_json_array(raw: str) -> list[dict]:
    """작은 모델은 JSON 앞뒤에 말을 붙이거나 코드블록으로 감싼다. 방어적으로 파싱."""
    text = raw.strip()

    fenced = _FENCE_RE.search(text)
    if fenced:
        text = fenced.group(1).strip()

    if not text.startswith("["):
        start, end = text.find("["), text.rfind("]")
        if start == -1 or end <= start:
            raise ValueError("JSON 배열을 찾지 못했다")
        text = text[start:end + 1]

    parsed = json.loads(text)
    if not isinstance(parsed, list):
        raise ValueError("배열이 아니다")
    return [item for item in parsed if isinstance(item, dict)]


# --- 검증 · 중복 제거 -------------------------------------------------------

# 생성물에 섞이면 안 되는 것들 (모델이 지시를 흘릴 때 나온다)
_PLACEHOLDER_RE = re.compile(r"(\[.*?\]|\{.*?\}|OOO|XXX|홍길동|○○|김철수|이영희)")
_CONTACT_RE = re.compile(r"(01[016-9][-\s]?\d{3,4}[-\s]?\d{4}|\d{6}-\d{7})")
# 프롬프트 지시문이 본문에 새어 들어온 흔적. 학부모 민원에는 나올 수 없는 단어들.
_LEAK_RE = re.compile(r"(어조|카테고리|JSON|출력 형식|지시문|필수\]|~로 쓴다)")

MIN_BODY, MAX_BODY = 15, 600


def normalize(text: str) -> str:
    """중복 판정용 정규화 — 공백·문장부호를 제거해 '거의 같은 문장'을 잡는다."""
    text = unicodedata.normalize("NFKC", text)
    return re.sub(r"[\s\W_]+", "", text)


def validate(item: dict, category: str, tone: tuple[str, str]) -> tuple[dict | None, str]:
    """returns (record, reject_reason). record 가 None 이면 버린다.

    tone 은 이 항목에 **지시한** 어조 (이름, 위험도). 모델이 되돌려준 값이 아니라
    스크립트가 요청한 값이므로 본문 오염과 무관하다.
    """
    body = str(item.get("body", "")).strip()
    title = str(item.get("title", "")).strip()

    if not body:
        return None, "본문 없음"
    if len(body) < MIN_BODY:
        return None, f"본문이 너무 짧음({len(body)}자)"
    if len(body) > MAX_BODY:
        return None, f"본문이 너무 긺({len(body)}자)"
    if _PLACEHOLDER_RE.search(body) or _PLACEHOLDER_RE.search(title):
        return None, "플레이스홀더·가명 포함"
    if _CONTACT_RE.search(body):
        return None, "연락처·주민번호 형태 포함"
    if _LEAK_RE.search(body):
        return None, "프롬프트 지시문 유출"

    # 라벨-내용 불일치 방어 — 라벨이 프롬프트에서 오므로 주제 이탈은 곧 오라벨이다.
    signals = REQUIRED_SIGNALS.get(category, [])
    if signals and not any(s in body for s in signals):
        return None, f"라벨({category}) 신호 없음 — 주제 이탈 의심"

    tone_name, risk_hint = tone
    return {
        "category": category,
        "title": title[:80] or None,
        "body": body,
        # 지시한 어조에서 유도한 위험도 힌트. F2 학습의 약라벨(weak label)로 쓸 수
        # 있으나 정답은 아니다 — 사람 검수 전에는 참고값으로만 다룰 것.
        "risk_hint": risk_hint,
        "tone": tone_name,
        "source": "synthetic",
    }, ""


def split_bucket(body: str, eval_ratio: float) -> str:
    """본문 해시로 결정론적 분할. 재실행해도 같은 문장은 같은 쪽에 간다."""
    if eval_ratio <= 0:
        return "train"
    digest = hashlib.sha1(normalize(body).encode("utf-8")).hexdigest()
    return "eval" if (int(digest[:8], 16) % 1000) / 1000.0 < eval_ratio else "train"


# --- F3 오차단 측정 (선택) --------------------------------------------------

def check_filter(records: list[dict]) -> None:
    """생성된 '정당한 민원'이 F3 필터에 차단되는지 측정한다.

    합성 데이터는 정의상 전부 정당한 민원이므로, 차단되면 그게 곧 오차단이다.
    F3 패턴을 수정할 때 이 수치를 회귀 지표로 쓸 수 있다.
    """
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from app.services.ai.content_filter import filter_content
    except Exception as exc:
        print(f"\n[--check-filter] 건너뜀 — 백엔드 의존성을 불러올 수 없다: {exc}")
        return

    blocked = [
        (r, filter_content(r["body"]))
        for r in records
    ]
    hits = [(r, f) for r, f in blocked if f.is_blocked]

    print(f"\n=== F3 오차단 측정 ===")
    print(f"  검사 {len(records)}건 / 차단 {len(hits)}건 "
          f"({len(hits) / max(1, len(records)) * 100:.1f}%)")
    for r, f in hits[:10]:
        print(f"  ❌ [{r['category']}] {f.matched_terms} :: {r['body'][:60]}...")
    if not hits:
        print("  ✅ 오차단 없음")


# --- main -------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(
        description="합성 학부모 민원 생성 (F1 분류기 학습·평가용)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--count", type=int, default=20,
                   help="카테고리당 목표 건수 (기본 20)")
    p.add_argument("--batch", type=int, default=5,
                   help="한 번의 LLM 호출로 받을 건수 (기본 5, 작은 모델은 작게)")
    p.add_argument("--model", default="gemma3:4b", help="모델 이름 (기본 gemma3:4b)")
    p.add_argument("--base-url", default="http://localhost:11434/v1",
                   help="OpenAI 호환 엔드포인트 (기본 Ollama)")
    p.add_argument("--temperature", type=float, default=1.0,
                   help="다양성 확보를 위해 기본값을 높게 둔다")
    p.add_argument("--timeout", type=float, default=180.0, help="호출 타임아웃(초)")
    p.add_argument("--out", default="data/synthetic_complaints.jsonl",
                   help="출력 JSONL 경로 (backend/ 기준 상대경로)")
    p.add_argument("--eval-ratio", type=float, default=0.0,
                   help="평가셋 비율(예: 0.2). 주면 .train/.eval 로 나눠 쓴다")
    p.add_argument("--categories", nargs="*", default=CATEGORIES,
                   help=f"생성할 카테고리 (기본 전체: {' '.join(CATEGORIES)})")
    p.add_argument("--check-filter", action="store_true",
                   help="생성물이 F3 필터에 오차단되는지 측정")
    args = p.parse_args()

    bad = [c for c in args.categories if c not in CATEGORIES]
    if bad:
        print(f"알 수 없는 카테고리: {bad}\n사용 가능: {CATEGORIES}", file=sys.stderr)
        return 2

    print(f"모델 {args.model} @ {args.base_url}")
    print(f"카테고리 {len(args.categories)}개 × {args.count}건 목표\n")

    records: list[dict] = []
    seen: set[str] = set()
    rejects: dict[str, int] = {}

    for category in args.categories:
        made, variety, attempts = 0, 0, 0
        # 무한 루프 방지 — 목표의 4배까지만 시도한다.
        max_attempts = max(6, (args.count // max(1, args.batch)) * 4)

        while made < args.count and attempts < max_attempts:
            attempts += 1
            variety += 1
            want = min(args.batch, args.count - made)
            try:
                raw = call_llm(
                    args.base_url, args.model,
                    build_prompt(category, want, variety),
                    args.temperature, args.timeout,
                )
                items = extract_json_array(raw)
            except urllib.error.URLError as exc:
                print(f"\n엔드포인트에 연결할 수 없다: {exc}", file=sys.stderr)
                print(f"  ollama serve 가 떠 있는지, --base-url 이 맞는지 확인.", file=sys.stderr)
                return 1
            except Exception as exc:
                rejects[f"응답 파싱 실패: {type(exc).__name__}"] = \
                    rejects.get(f"응답 파싱 실패: {type(exc).__name__}", 0) + 1
                continue

            # 지시한 어조를 순서대로 대응시킨다(모델이 순서를 지킨다는 가정).
            # 개수가 어긋나면 남는 항목은 마지막 어조로 처리한다.
            batch_tones = pick_tones(want, variety)
            for idx, item in enumerate(items):
                if made >= args.count:
                    break
                tone = batch_tones[min(idx, len(batch_tones) - 1)]
                record, reason = validate(item, category, tone)
                if record is None:
                    rejects[reason] = rejects.get(reason, 0) + 1
                    continue
                key = normalize(record["body"])
                if key in seen:
                    rejects["중복"] = rejects.get("중복", 0) + 1
                    continue
                seen.add(key)
                record["split"] = split_bucket(record["body"], args.eval_ratio)
                records.append(record)
                made += 1

        print(f"  {category:18s} {made}/{args.count}  (호출 {attempts}회)"
              f"{'  ⚠️ 목표 미달 — 신호 없는 응답이 많다면 프롬프트를 손볼 것'
                 if made < args.count else ''}")

    if not records:
        print("\n생성된 레코드가 없다. 모델 응답 형식을 확인할 것.", file=sys.stderr)
        return 1

    stamp = datetime.now(timezone.utc).isoformat()
    for r in records:
        r["model"] = args.model
        r["generated_at"] = stamp

    out_path = Path(__file__).resolve().parent.parent / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if args.eval_ratio > 0:
        groups = {"train": [], "eval": []}
        for r in records:
            groups[r["split"]].append(r)
        for name, rows in groups.items():
            path = out_path.with_suffix(f".{name}.jsonl")
            path.write_text(
                "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                encoding="utf-8",
            )
            print(f"\n{name}: {len(rows)}건 → {path}")
    else:
        out_path.write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records),
            encoding="utf-8",
        )
        print(f"\n{len(records)}건 → {out_path}")

    print("\n=== 카테고리 분포 ===")
    for category in args.categories:
        n = sum(1 for r in records if r["category"] == category)
        print(f"  {category:18s} {n:4d}")
    print("=== 위험도 힌트 분포 ===")
    for risk in ("low", "medium", "high"):
        n = sum(1 for r in records if r["risk_hint"] == risk)
        print(f"  {risk:18s} {n:4d}")
    if rejects:
        print("=== 버린 응답 ===")
        for reason, n in sorted(rejects.items(), key=lambda kv: -kv[1]):
            print(f"  {reason:30s} {n:4d}")

    if args.check_filter:
        check_filter(records)

    print("\n⚠️ 합성 데이터다. 실제 민원과 분포가 다르므로 평가 결과를 과신하지 말고,")
    print("   학습에 쓰기 전에 표본을 사람이 검수할 것. (source=\"synthetic\")")
    return 0


if __name__ == "__main__":
    sys.exit(main())
