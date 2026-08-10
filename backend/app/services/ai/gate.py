"""자동 응대 게이트 — "AI 판단만으로 처리해도 되는가"를 정하는 안전장치.

접수 파이프라인에서 '단순 행정'으로 분류된 민원은 챗봇 자동 응대 후보가 된다.
그런데 이 판단이 틀렸을 때의 비용은 **심하게 비대칭**이다.

- 학교폭력 민원을 '단순 행정'으로 오분류 → 자동 응대되고 **교사에게 영원히 안 간다** (재앙)
- 단순 행정을 '그 외'로 오분류 → 교사가 한 번 더 볼 뿐 (경미)

그래서 이 게이트는 자동 응대 쪽으로만 보수적이다. 조금이라도 의심스러우면
사람(교사)에게 보낸다. 오차단보다 과잉전달을 택한다.

기획 문서(docs/project-overview.md §4)의 이 대목이 구현되는 지점이다:
    "정확도보다 틀렸을 때의 안전장치(사람 재검토·이의제기 경로)가 더 중요"

네 조건을 **모두** 통과해야 자동 응대한다:
  1. 단순 행정으로 분류됨
  2. 자동 응대 금지 신호가 없음 (결정론적 안전망)
  3. 위험도가 high/critical 이 아님 (F2 교차 검증)
  4. 분류 신뢰도가 임계값 이상 (AUTO_ANSWER_MIN_CONFIDENCE)

2번이 규칙 기반인 이유는 F3 욕설 필터와 같다. 아동 안전이 걸린 판정을 확률적
모델에만 맡기지 않는다. 또한 F2 위험 탐지는 '공격성'을 보므로, **차분하게 서술된
심각한 사안**(예: "아이가 반 친구에게 지속적으로 괴롭힘을 당해 상담 요청합니다")은
위험도가 낮게 나온다. 2번이 그 빈틈을 메운다.
"""

from dataclasses import dataclass

from app.core.config import settings
from app.services.ai.classifier import VIOLENCE_KEYWORDS

# 자동 응대해서는 안 되는 사안 신호.
# F2 공격성 점수로는 잡히지 않는(차분하게 쓰인) 아동 안전·성 관련·자해 사안을 막는다.
# 학교폭력·분쟁 신호는 분류기와 같은 목록을 공유한다(단일 소스).
_SAFETY_VETO_KEYWORDS = [
    *VIOLENCE_KEYWORDS,
    # 자해·자살
    "자살", "자해", "죽고 싶", "죽고싶", "극단적 선택",
    # 성 관련
    "성희롱", "성폭력", "성추행", "몰카", "불법촬영", "성적 수치",
    # 아동학대·방임
    "학대", "방임", "체벌",
]

# 사람이 반드시 봐야 하는 위험도 — 이 수준이면 내용이 단순 행정이어도 교사에게 보낸다.
_HUMAN_REVIEW_RISK = ("high", "critical")

AUTO_ANSWER_CATEGORY = "administrative"


@dataclass
class GateDecision:
    """자동 응대 가능 여부와 그 근거.

    reason 은 사람이 읽는 감사·디버깅용 문구다. 자동 응대를 막은 이유를
    로그로 남겨 두면 나중에 임계값을 조정할 때 근거가 된다.
    """

    can_auto_answer: bool
    reason: str


def evaluate_auto_answer(
    text: str,
    category: str | None,
    confidence: float | None,
    risk: str,
) -> GateDecision:
    """자동 응대해도 되는지 판정한다. 확신이 없으면 항상 False."""
    if category != AUTO_ANSWER_CATEGORY:
        return GateDecision(False, f"단순 행정이 아님(분류={category})")

    matched = [kw for kw in _SAFETY_VETO_KEYWORDS if kw in text]
    if matched:
        return GateDecision(False, f"자동 응대 금지 신호 감지: {', '.join(matched)}")

    if risk in _HUMAN_REVIEW_RISK:
        return GateDecision(False, f"위험도 {risk} — 사람 확인 필요")

    threshold = settings.auto_answer_min_confidence
    if confidence is None:
        return GateDecision(False, "분류 신뢰도 없음")
    if confidence < threshold:
        return GateDecision(False, f"분류 신뢰도 부족({confidence:.2f} < {threshold:.2f})")

    return GateDecision(
        True,
        f"단순 행정 · 신뢰도 {confidence:.2f} ≥ {threshold:.2f} · 위험도 {risk}",
    )
