"""합성 데이터 생성기의 계약 테스트.

생성기는 표준 라이브러리만 쓰도록(백엔드 venv 없이 돌게) 카테고리 목록을 자체
보유한다. 그 목록이 분류기와 어긋나면 학습 라벨과 서비스 라벨이 달라지는
조용한 사고가 나므로 여기서 묶어둔다.

검증 로직(중복 제거·플레이스홀더 거부 등)도 LLM 호출 없이 테스트한다.
"""

import importlib.util
from pathlib import Path

import pytest

from app.services.ai.classifier import CATEGORIES as CLASSIFIER_CATEGORIES

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "gen_synthetic_complaints.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("gen_synthetic_complaints", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # __main__ 가드가 있어 부작용 없음
    return module


gen = _load_script()


def test_카테고리_목록이_분류기와_일치():
    assert gen.CATEGORIES == CLASSIFIER_CATEGORIES, (
        "생성기와 분류기의 카테고리가 어긋나면 학습 라벨이 서비스와 달라진다"
    )


def test_모든_카테고리에_생성_지침이_있다():
    assert set(gen.CATEGORY_GUIDE) == set(gen.CATEGORIES)


def test_어조의_위험도_힌트가_유효한_값():
    valid = {"low", "medium", "high", "critical"}
    assert {risk for _, risk in gen.TONES} <= valid


# --- 검증 로직 --------------------------------------------------------------


LOW_TONE = ("정중하고 차분한", "low")
HIGH_TONE = ("여러 번 문의했다며 답답함을 드러내는", "high")


def test_정상_레코드는_통과():
    record, reason = gen.validate(
        {"title": "급식 문의", "body": "다음 주 급식 식단표를 어디서 확인할 수 있는지 알고 싶습니다."},
        "administrative",
        LOW_TONE,
    )
    assert record is not None, reason
    assert record["category"] == "administrative"
    assert record["source"] == "synthetic", "실제 데이터와 구분되는 표시가 반드시 있어야 한다"
    assert record["risk_hint"] == "low"


def test_위험도는_지시한_어조에서_온다():
    """모델 응답이 아니라 스크립트가 지시한 값을 쓴다(본문 오염 방지 설계)."""
    record, _ = gen.validate(
        {"title": "t", "body": "급식 식단표 확인 방법을 여러 번 문의드렸습니다. 답변 부탁드립니다."},
        "administrative",
        HIGH_TONE,
    )
    assert record is not None
    assert record["risk_hint"] == "high"
    assert record["tone"] == HIGH_TONE[0]


@pytest.mark.parametrize(
    "body,이유",
    [
        ("", "본문 없음"),
        ("짧다", "너무 짧음"),
        ("가" * 700, "너무 긺"),
        ("저희 아이 홍길동이 급식에 대해 문의드립니다. 확인 부탁드립니다.", "가명 포함"),
        ("[학생 이름]의 급식 관련해 문의드립니다. 확인 부탁드립니다.", "플레이스홀더 포함"),
        ("급식 문의드립니다. 연락처는 010-1234-5678 입니다. 회신 부탁드립니다.", "연락처 포함"),
        ("OOO 학생 급식 관련 문의드립니다. 확인 부탁드립니다.", "가명 포함"),
        # 실제로 발생했던 프롬프트 유출 — 학습 데이터에 들어가면 분류기가
        # '어조로'를 특징으로 배운다.
        ("아쉬움을 표현하는 어조로, 급식 식단표 발급 절차를 문의드립니다.", "지시문 유출"),
        ("사무적이고 간결한 어조로, 결석 증명서 발급을 신청합니다.", "지시문 유출"),
    ],
)
def test_불량_레코드는_거부(body, 이유):
    record, reason = gen.validate({"title": "t", "body": body}, "administrative", LOW_TONE)
    assert record is None, f"{이유} 인데 통과했다: {body[:40]}"
    assert reason, "거부 이유가 비어 있다"


# --- 라벨 이탈 방어 ---------------------------------------------------------


def test_라벨_신호가_없으면_거부():
    """violence_dispute 라벨인데 학습 상담 내용 — 실제로 발생한 오라벨."""
    record, reason = gen.validate(
        {"title": "상담 요청",
         "body": "저희 아이가 수업 내용 숙지에 어려움을 겪고 학업이 떨어지는 상황입니다. 지원 방안을 마련해 주실 수 있을까요?"},
        "violence_dispute",
        LOW_TONE,
    )
    assert record is None, "주제를 벗어난 표본이 violence_dispute 라벨로 통과했다"
    assert "신호 없음" in reason


def test_라벨_신호가_있으면_통과():
    record, reason = gen.validate(
        {"title": "괴롭힘 상담",
         "body": "저희 아이가 같은 반 학생들에게 지속적으로 괴롭힘을 당하고 있다고 합니다. 상담을 요청드립니다."},
        "violence_dispute",
        LOW_TONE,
    )
    assert record is not None, reason


def test_other_는_신호를_요구하지_않는다():
    """포괄 카테고리라 요구 신호가 없다."""
    record, reason = gen.validate(
        {"title": "분실물", "body": "아이가 우산을 학교에 두고 온 것 같습니다. 확인할 방법이 있을까요?"},
        "other",
        LOW_TONE,
    )
    assert record is not None, reason


def test_어조_선택은_결정론적이고_순환한다():
    assert gen.pick_tones(3, 0) == gen.pick_tones(3, 0)
    # 한 배치 안에서 서로 다른 어조가 배정되어야 한다(위험도가 low 로 쏠리지 않게)
    assert len({t for t, _ in gen.pick_tones(len(gen.TONES), 0)}) == len(gen.TONES)


# --- 중복 판정 --------------------------------------------------------------


def test_공백_문장부호만_다르면_같은_문장으로_본다():
    a = gen.normalize("급식 식단표를 확인하고 싶습니다.")
    b = gen.normalize("급식   식단표를 확인하고 싶습니다!!")
    assert a == b


def test_내용이_다르면_다른_문장():
    assert gen.normalize("급식 문의입니다") != gen.normalize("성적 문의입니다")


# --- 결정론적 분할 ----------------------------------------------------------


def test_같은_본문은_항상_같은_쪽으로_분할():
    body = "저희 아이 수행평가 채점 기준을 알고 싶어 문의드립니다."
    assert gen.split_bucket(body, 0.2) == gen.split_bucket(body, 0.2)


def test_분할_비율이_0이면_전부_train():
    assert gen.split_bucket("아무 본문이든", 0.0) == "train"


def test_분할이_대략_비율을_따른다():
    bodies = [f"민원 본문 예시 번호 {i} 입니다. 확인 부탁드립니다." for i in range(500)]
    evals = sum(1 for b in bodies if gen.split_bucket(b, 0.2) == "eval")
    assert 0.1 < evals / len(bodies) < 0.3, f"평가셋 비율이 크게 벗어남: {evals}/500"


# --- LLM 응답 파싱 ----------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        '[{"title":"t","body":"b"}]',
        '```json\n[{"title":"t","body":"b"}]\n```',
        '```\n[{"title":"t","body":"b"}]\n```',
        '네, 요청하신 민원입니다:\n[{"title":"t","body":"b"}]\n필요하면 더 만들어 드릴게요.',
    ],
)
def test_작은_모델의_군더더기를_벗겨낸다(raw):
    items = gen.extract_json_array(raw)
    assert items == [{"title": "t", "body": "b"}]


@pytest.mark.parametrize("raw", ["", "JSON 못 만들겠습니다", "{}", "[[["])
def test_파싱_불가는_예외(raw):
    with pytest.raises(Exception):
        gen.extract_json_array(raw)


def test_배열_속_비객체는_걸러진다():
    assert gen.extract_json_array('[{"body":"b"}, "쓰레기", 42]') == [{"body": "b"}]
