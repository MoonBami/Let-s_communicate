"""자동 응대 게이트 회귀 테스트.

이 게이트가 뚫리면 '학교폭력 민원이 자동 응대되고 교사에게 안 가는' 사고가
난다. 그래서 통과 케이스보다 **차단 케이스**를 촘촘히 고정한다.

DB·네트워크 없이 도는 순수 함수 테스트다:
    cd backend && pytest
"""

import pytest

from app.core.config import settings
from app.services.ai.gate import evaluate_auto_answer

# 게이트를 통과할 수 있는 기준 신뢰도 (임계값보다 확실히 높게)
HIGH = min(1.0, settings.auto_answer_min_confidence + 0.2)
LOW = max(0.0, settings.auto_answer_min_confidence - 0.2)

PLAIN_ADMIN_TEXT = "다음 주 현장학습 동의서 제출 기한이 언제인지 알고 싶습니다."


def test_통과_단순행정_고신뢰도_저위험():
    d = evaluate_auto_answer(PLAIN_ADMIN_TEXT, "administrative", HIGH, "low")
    assert d.can_auto_answer
    assert "단순 행정" in d.reason


def test_통과_임계값_경계는_포함():
    d = evaluate_auto_answer(
        PLAIN_ADMIN_TEXT, "administrative", settings.auto_answer_min_confidence, "low"
    )
    assert d.can_auto_answer, "임계값과 같으면 통과해야 한다(>= 비교)"


@pytest.mark.parametrize(
    "category", ["learning", "life", "grades", "violence_dispute", "other", None]
)
def test_차단_단순행정이_아니면_전부(category):
    d = evaluate_auto_answer(PLAIN_ADMIN_TEXT, category, HIGH, "low")
    assert not d.can_auto_answer


def test_차단_신뢰도_부족():
    d = evaluate_auto_answer(PLAIN_ADMIN_TEXT, "administrative", LOW, "low")
    assert not d.can_auto_answer
    assert "신뢰도 부족" in d.reason


def test_차단_신뢰도_없음():
    d = evaluate_auto_answer(PLAIN_ADMIN_TEXT, "administrative", None, "low")
    assert not d.can_auto_answer


@pytest.mark.parametrize("risk", ["high", "critical"])
def test_차단_위험도_높으면_사람_확인(risk):
    """내용이 단순 행정이어도 화가 많이 난 학부모는 사람이 응대해야 한다."""
    d = evaluate_auto_answer(PLAIN_ADMIN_TEXT, "administrative", HIGH, risk)
    assert not d.can_auto_answer
    assert risk in d.reason


@pytest.mark.parametrize("risk", ["low", "medium"])
def test_통과_위험도_보통까지는_허용(risk):
    """'부탁드립니다' 같은 표현만으로 medium 이 되므로 여기까지는 막지 않는다."""
    assert evaluate_auto_answer(PLAIN_ADMIN_TEXT, "administrative", HIGH, risk).can_auto_answer


# --- 핵심: 차분하게 쓰인 심각한 사안 (F2 공격성 점수로는 안 잡히는 것들) ---
# 전부 '단순 행정 + 고신뢰도 + 저위험'이라는 최악의 조합으로 들어와도 막혀야 한다.
@pytest.mark.parametrize(
    "text",
    [
        "아이가 반 친구에게 지속적으로 괴롭힘을 당하고 있어 상담을 요청합니다.",
        "학폭 신고 절차에 대한 서류를 안내받고 싶습니다.",
        "같은 반 학생이 아이를 때리는 일이 반복되고 있습니다.",
        "아이가 요즘 자해를 하는 것 같아 걱정입니다.",
        "아이가 죽고 싶다는 말을 했습니다.",
        "교실에서 성희롱으로 느껴지는 일이 있었습니다.",
        "체벌이 있었다고 아이가 말합니다.",
        "가정에서 학대가 의심되는 아이가 있어 문의드립니다.",
    ],
)
def test_차단_안전_거부어가_있으면_무조건(text):
    d = evaluate_auto_answer(text, "administrative", 1.0, "low")
    assert not d.can_auto_answer, f"자동 응대되면 안 되는 내용이 통과했다: {text}"
    assert "금지 신호" in d.reason


def test_거부어_판정이_다른_조건보다_우선():
    """신뢰도·위험도가 완벽해도 안전 신호가 이긴다."""
    d = evaluate_auto_answer("학폭 관련 서류 문의입니다.", "administrative", 1.0, "low")
    assert not d.can_auto_answer
    assert "금지 신호" in d.reason


def test_평범한_행정민원은_거부어에_걸리지_않는다():
    """과잉 차단 방지 — 정상적인 행정 문의는 통과해야 한다."""
    for text in [
        "급식 식단표를 어디서 확인할 수 있나요?",
        "졸업증명서 발급 방법을 알고 싶습니다.",
        "방과후 수업 신청 기간이 궁금합니다.",
        "교복 구매 지원금 신청 서류를 문의드립니다.",
    ]:
        assert evaluate_auto_answer(text, "administrative", HIGH, "low").can_auto_answer, text
