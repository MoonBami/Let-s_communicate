"""F2: 감정 분석 · 위험 탐지.

민원 원문의 감정(긍정/부정)과 공격성을 추정해 위험도(low~critical)를 매긴다.
위험도는 교사 민원함의 우선순위·강조 표시에 쓰인다.

키가 있으면 Claude로 뉘앙스까지 판단하고, 없으면 키워드 휴리스틱으로 fallback한다.
필터(F3)와 달리 위험도는 '판단'이라 확률적 모델을 써도 되지만, 서비스가 죽지
않도록 파싱/네트워크 실패 시 항상 fallback으로 떨어진다.
"""

from dataclasses import dataclass, field

from app.core.config import settings
from app.services.ai.client import call_claude_json

RISK_LEVELS = ["low", "medium", "high", "critical"]

SYSTEM_PROMPT = """너는 학교 민원의 감정과 위험도를 분석하는 보조 시스템이다.
민원 원문을 읽고 JSON으로만 답하라.

판단 기준:
- sentiment_score: -1(매우 부정) ~ 1(매우 긍정)
- aggression_score: 0(차분) ~ 1(매우 공격적)
- risk: low(단순 문의) / medium(불만·항의) / high(반복 항의·강한 분노) / critical(위협·신변 위해 암시)
- reasons: 그렇게 판단한 근거를 한국어 짧은 문구 배열로

출력 형식(JSON만):
{"sentiment_score": <-1~1>, "aggression_score": <0~1>, "risk": "<low|medium|high|critical>", "reasons": ["..."]}
"""

# fallback용 공격성/분노 신호 키워드 (강→약)
_CRITICAL_WORDS = ["죽", "협박", "가만", "고소", "언론", "국민신문고", "감사원"]
_HIGH_WORDS = ["당장", "책임져", "용납", "절대", "무능", "따지", "항의", "화가", "분노", "참을 수"]
_MEDIUM_WORDS = ["불만", "실망", "이해가 안", "왜", "문제", "부탁", "시정", "개선"]


@dataclass
class RiskResult:
    sentiment_score: float
    aggression_score: float
    risk: str
    model_name: str
    reasons: list[str] = field(default_factory=list)


def analyze_risk(text: str) -> RiskResult:
    data = call_claude_json(
        system=SYSTEM_PROMPT,
        user_content=text,
        model=settings.ai_classify_model,
        max_tokens=400,
        caller="F2.risk",
    )
    if data is None:
        return _fallback(text)

    risk = data.get("risk", "low")
    if risk not in RISK_LEVELS:
        risk = "low"
    reasons = data.get("reasons", [])
    if not isinstance(reasons, list):
        reasons = [str(reasons)]
    try:
        return RiskResult(
            sentiment_score=_clamp(float(data.get("sentiment_score", 0.0)), -1.0, 1.0),
            aggression_score=_clamp(float(data.get("aggression_score", 0.0)), 0.0, 1.0),
            risk=risk,
            model_name=settings.ai_classify_model,
            reasons=[str(r) for r in reasons][:8],
        )
    except (TypeError, ValueError):
        return _fallback(text)


def _fallback(text: str) -> RiskResult:
    reasons: list[str] = []
    risk = "low"
    aggression = 0.1

    if any(w in text for w in _CRITICAL_WORDS):
        risk, aggression = "critical", 0.9
        reasons.append("위협·강경 대응 암시 키워드 감지")
    elif any(w in text for w in _HIGH_WORDS):
        risk, aggression = "high", 0.65
        reasons.append("강한 분노·항의 표현 감지")
    elif any(w in text for w in _MEDIUM_WORDS):
        risk, aggression = "medium", 0.4
        reasons.append("불만·문제 제기 표현 감지")
    else:
        reasons.append("특이 신호 없음")

    # 느낌표/물음표 과다는 감정 격앙 신호로 가중
    if text.count("!") + text.count("?") >= 3:
        aggression = min(1.0, aggression + 0.15)
        reasons.append("감정 격앙 문장부호 다수")

    sentiment = -0.6 if risk in ("high", "critical") else (-0.3 if risk == "medium" else 0.0)
    return RiskResult(
        sentiment_score=sentiment,
        aggression_score=round(aggression, 2),
        risk=risk,
        model_name="rule-risk-v1",
        reasons=reasons,
    )


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))
