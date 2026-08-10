#!/usr/bin/env python3
"""F1 분류기 평가 하네스 — 무엇을 '잘한다'고 할지 정의한다.

## 왜 정확도만으로는 안 되는가

이 시스템에서 오분류의 비용은 심하게 비대칭이다. 전체 정확도 95% 인 분류기가
학교폭력 민원만 골라서 틀리면 최악이고, 정확도 80% 여도 위험한 민원을 절대
놓치지 않으면 훨씬 낫다.

그래서 이 하네스는 세 층으로 나눠 보고한다.

  1. 일반 지표    — 카테고리별 정밀도·재현율·F1, 혼동행렬. 모델 품질의 기본
  2. **치명 오류** — 학교폭력·분쟁을 '단순 행정'으로 예측한 비율.
                     이 경로만이 자동 응대로 이어져 민원이 교사에게 가지 않는다
  3. **최종 안전** — 분류기 + 자동응대 게이트를 통과시켜, 실제로 자동 응대될
                     위험 민원이 몇 건인지. 게이트가 방어선이므로 이 수치가 진짜 지표다

2번이 0 이 아니어도 3번이 0 이면 게이트가 막아준 것이다. 반대로 3번이 0 이 아니면
배포하면 안 된다. `--max-unsafe` 로 임계값을 넘으면 종료코드 1 을 돌려주므로
나중에 CI 에 걸 수 있다.

## 기준선(baseline)의 의미

모델을 만들기 전에 **지금의 규칙 기반 fallback 분류기**를 먼저 측정해 둔다.
새 모델이 이 숫자를 못 넘으면 만든 의미가 없다. 학습을 시작하기 전에 이 스크립트를
한 번 돌려 baseline 을 기록하는 것이 순서다.

## 실행

백엔드 의존성이 필요하다(분류기·게이트를 실제로 호출하므로).

    # 평가셋 생성 (아직 없으면)
    python scripts/gen_synthetic_complaints.py --count 30 --eval-ratio 0.2

    # 규칙 기반 fallback 기준선 측정
    python scripts/eval_classifier.py --data data/synthetic_complaints.eval.jsonl

    # 실제 LLM 경로로 측정 (.env 에 ANTHROPIC_API_KEY 필요)
    ANTHROPIC_API_KEY=... python scripts/eval_classifier.py --data ...

입력은 `gen_synthetic_complaints.py` 가 만든 JSONL(`category`, `body` 필드)이며,
사람이 검수한 실제 민원 데이터도 같은 형식이면 그대로 쓸 수 있다.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.ai.classifier import CATEGORIES, classify  # noqa: E402
from app.services.ai.gate import evaluate_auto_answer  # noqa: E402

# 자동 응대로 이어지는 유일한 카테고리 — 여기로 잘못 예측되는 것이 위험하다.
AUTO_ANSWER_CATEGORY = "administrative"

# 자동 응대되면 안 되는 '위험한 진짜 라벨'. 이 라벨이 administrative 로 예측되는 것이
# 치명 오류다. life 를 포함한 이유: 생활지도 민원도 아이 문제라 사람이 봐야 한다.
SENSITIVE_TRUE = ("violence_dispute",)


# --- 지표 계산 (순수 함수 — tests/test_eval_classifier.py 가 검사한다) --------

def confusion(pairs: list[tuple[str, str]]) -> dict[tuple[str, str], int]:
    """(정답, 예측) → 건수."""
    return dict(Counter(pairs))


def per_class_metrics(pairs: list[tuple[str, str]]) -> dict[str, dict[str, float]]:
    """카테고리별 precision·recall·f1·support."""
    tp: Counter[str] = Counter()
    fp: Counter[str] = Counter()
    fn: Counter[str] = Counter()
    support: Counter[str] = Counter()

    for true, pred in pairs:
        support[true] += 1
        if true == pred:
            tp[true] += 1
        else:
            fp[pred] += 1
            fn[true] += 1

    out: dict[str, dict[str, float]] = {}
    for category in CATEGORIES:
        p_denom = tp[category] + fp[category]
        r_denom = tp[category] + fn[category]
        precision = tp[category] / p_denom if p_denom else 0.0
        recall = tp[category] / r_denom if r_denom else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        out[category] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": float(support[category]),
        }
    return out


def accuracy(pairs: list[tuple[str, str]]) -> float:
    return sum(1 for t, p in pairs if t == p) / len(pairs) if pairs else 0.0


def macro_f1(metrics: dict[str, dict[str, float]]) -> float:
    """support 가 0 인 카테고리는 제외한다(평가셋에 없는 라벨이 평균을 깎지 않도록)."""
    scored = [m["f1"] for m in metrics.values() if m["support"] > 0]
    return sum(scored) / len(scored) if scored else 0.0


def critical_errors(pairs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """민감한 진짜 라벨이 자동응대 카테고리로 예측된 경우."""
    return [
        (t, p) for t, p in pairs
        if t in SENSITIVE_TRUE and p == AUTO_ANSWER_CATEGORY
    ]


# --- 출력 -------------------------------------------------------------------

def print_confusion(pairs: list[tuple[str, str]]) -> None:
    matrix = confusion(pairs)
    present = [c for c in CATEGORIES if any(t == c for t, _ in pairs)]
    width = max((len(c) for c in CATEGORIES), default=10)

    print("\n=== 혼동행렬 (행=정답, 열=예측) ===")
    header = " " * (width + 2) + "".join(f"{c[:6]:>8s}" for c in CATEGORIES)
    print(header)
    for true in present:
        row = f"  {true:<{width}s}"
        for pred in CATEGORIES:
            n = matrix.get((true, pred), 0)
            mark = ""
            if n and true in SENSITIVE_TRUE and pred == AUTO_ANSWER_CATEGORY:
                mark = "!"  # 치명 오류 위치
            row += f"{str(n) + mark:>8s}" if n else f"{'·':>8s}"
        print(row)


def main() -> int:
    p = argparse.ArgumentParser(description="F1 분류기 평가 (안전 지표 포함)")
    p.add_argument("--data", required=True, help="평가셋 JSONL (category, body 필드)")
    p.add_argument("--limit", type=int, default=0, help="앞에서 N건만 (0=전체)")
    p.add_argument("--confidence", type=float, default=None,
                   help="게이트 검사에 쓸 신뢰도 고정값. 미지정이면 분류기가 준 값을 쓴다. "
                        "실제 LLM 수준을 가정해 보려면 0.95 처럼 준다")
    p.add_argument("--max-unsafe", type=int, default=None,
                   help="자동 응대될 위험 민원이 이 건수를 넘으면 종료코드 1")
    p.add_argument("--show-errors", type=int, default=5, help="오분류 예시 표시 개수")
    args = p.parse_args()

    path = Path(args.data)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent.parent / path
    if not path.exists():
        print(f"평가셋이 없다: {path}", file=sys.stderr)
        print("먼저 scripts/gen_synthetic_complaints.py 로 생성할 것.", file=sys.stderr)
        return 2

    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("category") in CATEGORIES and row.get("body"):
            rows.append(row)
    if args.limit:
        rows = rows[:args.limit]
    if not rows:
        print("유효한 레코드가 없다.", file=sys.stderr)
        return 2

    synthetic = sum(1 for r in rows if r.get("source") == "synthetic")
    print(f"평가셋 {len(rows)}건  ({path.name})")
    if synthetic:
        print(f"  ⚠️ 합성 데이터 {synthetic}건 포함 — 실제 민원 분포와 다르므로 "
              f"이 점수를 실제 성능으로 읽지 말 것")

    pairs: list[tuple[str, str]] = []
    errors: list[tuple[str, str, str]] = []          # (정답, 예측, 본문)
    unsafe: list[tuple[str, str, str]] = []          # 자동 응대될 위험 민원
    model_names: Counter[str] = Counter()

    for i, row in enumerate(rows, 1):
        true, body = row["category"], row["body"]
        result = classify(body)
        pairs.append((true, result.category))
        model_names[result.model_name] += 1
        if true != result.category:
            errors.append((true, result.category, body))

        # 최종 안전 검사 — 분류 결과를 게이트에 통과시켜 본다.
        confidence = args.confidence if args.confidence is not None else result.confidence
        decision = evaluate_auto_answer(body, result.category, confidence, row.get("risk_hint", "low"))
        if decision.can_auto_answer and true in SENSITIVE_TRUE:
            unsafe.append((true, result.category, body))

        # 리다이렉트된 출력에서는 \r 이 남아 로그를 어지럽히므로 tty 에서만 표시한다.
        if sys.stdout.isatty():
            print(f"\r  분류 {i}/{len(rows)}", end="", flush=True)
    if sys.stdout.isatty():
        print()

    print(f"\n분류 경로: {', '.join(f'{m}×{n}' for m, n in model_names.most_common())}")

    metrics = per_class_metrics(pairs)
    acc, mf1 = accuracy(pairs), macro_f1(metrics)

    print("\n=== 1. 일반 지표 ===")
    print(f"  정확도        {acc:.3f}")
    print(f"  macro F1      {mf1:.3f}")
    print(f"\n  {'카테고리':<20s}{'정밀도':>8s}{'재현율':>8s}{'F1':>8s}{'건수':>7s}")
    for category in CATEGORIES:
        m = metrics[category]
        if m["support"] == 0:
            continue
        print(f"  {category:<20s}{m['precision']:>8.3f}{m['recall']:>8.3f}"
              f"{m['f1']:>8.3f}{int(m['support']):>7d}")

    print_confusion(pairs)

    crit = critical_errors(pairs)
    n_sensitive = sum(1 for t, _ in pairs if t in SENSITIVE_TRUE)
    print(f"\n=== 2. 치명 오류 (위험 민원 → '{AUTO_ANSWER_CATEGORY}' 오분류) ===")
    if n_sensitive == 0:
        print(f"  평가셋에 {SENSITIVE_TRUE} 표본이 없다 — 이 지표를 측정할 수 없다.")
        print("  ⚠️ 위험 카테고리 표본 없이 배포 판단을 하지 말 것.")
    else:
        rate = len(crit) / n_sensitive
        flag = "✅" if not crit else "🔴"
        print(f"  {flag} {len(crit)}/{n_sensitive}건 ({rate * 100:.1f}%)")

    print(f"\n=== 3. 최종 안전 (분류기 + 자동응대 게이트) ===")
    if unsafe:
        print(f"  🔴 자동 응대될 위험 민원 {len(unsafe)}건 — 배포 불가")
        for true, pred, body in unsafe[:args.show_errors]:
            print(f"     [{true} → {pred}] {body[:70]}...")
    else:
        print(f"  ✅ 0건 — 게이트가 모두 막았다")
        if crit:
            print(f"     (분류기는 {len(crit)}건 틀렸지만 게이트가 방어했다)")

    if errors and args.show_errors:
        print(f"\n=== 오분류 예시 (최대 {args.show_errors}건) ===")
        for true, pred, body in errors[:args.show_errors]:
            print(f"  [{true} → {pred}] {body[:70]}...")

    if args.max_unsafe is not None and len(unsafe) > args.max_unsafe:
        print(f"\n종료: 위험 민원 자동응대 {len(unsafe)}건 > 허용 {args.max_unsafe}건")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
