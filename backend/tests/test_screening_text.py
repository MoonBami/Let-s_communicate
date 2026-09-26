"""AI 파이프라인이 검사할 텍스트 구성 테스트.

제목을 빼먹으면 욕설·위협이 그대로 교사에게 전달된다(이슈 #18). 반대로 제목을
본문과 떼어 따로 검사하면 맥락이 사라져 오차단이 는다. 그래서 '합쳐서 한 번에'가
설계이며, 여기서 그 성질을 고정한다.

DB 없이 도는 순수 함수 테스트다.
"""

import pytest

from app.api.routes.complaints import screening_text
from app.services.ai.content_filter import filter_content
from app.services.ai.gate import evaluate_auto_answer

BODY = "확인 부탁드립니다."


# --- 구성 규칙 --------------------------------------------------------------


def test_제목이_있으면_본문과_함께_검사한다():
    assert screening_text("제목", "본문") == "제목\n본문"


@pytest.mark.parametrize("title", [None, "", "   "])
def test_제목이_없으면_본문만(title):
    assert screening_text(title, "본문") == "본문"


def test_제목_앞뒤_공백은_정리한다():
    assert screening_text("  제목  ", "본문") == "제목\n본문"


def test_본문은_그대로_보존된다():
    """증거로도 쓰이므로 본문이 변형되면 안 된다."""
    body = "  줄바꿈\n과  공백이   있는 본문  "
    assert body in screening_text("제목", body)


# --- 제목의 욕설·위협이 실제로 잡히는가 (이슈 #18) --------------------------


@pytest.mark.parametrize(
    "title",
    ["개새끼야", "너 죽여버릴거야", "씨발 가만 안 둬", "지랄하지 마라", "병신인가"],
)
def test_제목의_욕설_위협이_차단된다(title):
    result = filter_content(screening_text(title, BODY))
    assert result.is_blocked, f"제목 '{title}' 가 통과했다 — 교사 민원함에 그대로 뜬다"
    assert result.matched_terms


def test_제목에만_있어도_증거가_남을_내용에_포함된다():
    """raw_evidence 로 저장되는 텍스트에 제목이 들어 있어야 추적이 된다."""
    screened = screening_text("개새끼야", BODY)
    assert "개새끼야" in screened


def test_제목_본문에_걸쳐_있는_표현도_잡힌다():
    """'가만' 으로 끝나는 제목 + '안 둬' 로 시작하는 본문 같은 분할."""
    assert filter_content(screening_text("가만", "안 둘 거야")).is_blocked


# --- 오차단이 늘지 않았는가 (이쪽이 더 위험하다) ----------------------------

LEGITIMATE = [
    ("학교폭력 상담 요청", "같은 반 친구가 아이를 때려서 팔에 멍이 들었습니다."),
    ("때려서 다쳤습니다", "어제 점심시간에 있었던 일을 확인하고 싶습니다."),
    ("두들겨 맞았다고 합니다", "아이가 오늘 그렇게 말해서 걱정됩니다."),
    ("상담 방문 문의", "이번 주에 학교에 찾아가서 상담하고 싶습니다."),
    ("난방이 꺼져 있습니다", "교실이 추웠다고 아이가 말합니다."),
    ("제출 기한이 닥쳐서", "서류를 급하게 문의드립니다."),
    ("새끼손가락 부상", "아이가 다쳐서 깁스를 했습니다. 체육 수업을 문의드립니다."),
    ("정신병원 진료 관련", "아이가 상담 치료를 받고 있어 배려를 부탁드립니다."),
    ("급식 문의", "다음 주 식단표를 어디서 확인할 수 있나요?"),
    ("성적 이의", "수행평가 채점 기준을 알고 싶습니다."),
]


@pytest.mark.parametrize("title,body", LEGITIMATE)
def test_정당한_민원은_제목을_합쳐도_차단되지_않는다(title, body):
    result = filter_content(screening_text(title, body))
    assert not result.is_blocked, (
        f"정당한 민원이 차단됨(matched={result.matched_terms}): {title} / {body}"
    )


# --- 게이트도 제목을 본다 ---------------------------------------------------


def test_제목의_안전신호가_자동응대를_막는다():
    """본문만 보면 단순 행정으로 자동 응대될 민원을 제목이 막아야 한다."""
    screened = screening_text("학폭 신고 관련", "서류 신청 방법을 알고 싶습니다.")
    decision = evaluate_auto_answer(screened, "administrative", 0.95, "low")
    assert not decision.can_auto_answer
    assert "금지 신호" in decision.reason


def test_제목이_평범하면_자동응대_판정은_그대로():
    screened = screening_text("급식 문의", "다음 주 식단표를 어디서 확인할 수 있나요?")
    assert evaluate_auto_answer(screened, "administrative", 0.95, "low").can_auto_answer
