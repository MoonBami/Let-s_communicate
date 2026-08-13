"""F1: 민원 자동 분류.

핵심: '모델을 직접 학습'하는 게 아니라, LLM에 few-shot 프롬프트를 주고
JSON을 받아 파싱하는 방식. 키가 없으면 키워드 규칙 기반 fallback.
데이터가 쌓이면 이 인터페이스를 유지한 채 KoELECTRA 등으로 교체 가능.
"""

from dataclasses import dataclass

from app.core.config import settings
from app.services.ai.client import call_claude_json

CATEGORIES = ["administrative", "learning", "life", "grades", "violence_dispute", "other"]

SYSTEM_PROMPT = """너는 학교 민원을 분류하는 보조 시스템이다.
아래 카테고리 중 하나로만 분류하고, JSON으로만 답하라.

카테고리:
- administrative: 단순 행정(서류, 일정, 급식, 준비물 등)
- learning: 학습 지도
- life: 생활지도
- grades: 성적
- violence_dispute: 학교폭력·분쟁
- other: 위에 없음

출력 형식(JSON만): {"category": "<카테고리>", "confidence": <0~1>, "reason": "<간단한 근거>"}
"""

# 학교폭력·분쟁 신호. gate.py 의 '자동 응대 금지' 판정이 이 목록을 포함한다
# (같은 신호를 두 곳에서 따로 관리하면 한쪽만 갱신되는 사고가 난다).
#
# 활용형을 빠뜨리면 신고를 놓친다 — '때리'만 있으면 "때려서/때렸다/때린"이 안 걸린다.
# 이 목록의 오탐 비용은 낮다(교사에게 한 번 더 갈 뿐)이므로 넓게 잡는다.
VIOLENCE_KEYWORDS = [
    "폭력", "폭행", "협박", "싸움",
    "때리", "때려", "때렸", "때린",
    "괴롭", "왕따", "따돌",
    "학폭",
]

# 데이터가 없을 때 쓰는 아주 단순한 키워드 규칙(fallback)
_KEYWORDS = {
    "violence_dispute": VIOLENCE_KEYWORDS,
    "grades": ["성적", "점수", "등급", "시험", "채점"],
    "administrative": ["서류", "급식", "일정", "준비물", "증명서", "신청"],
    "learning": ["수업", "학습", "숙제", "진도", "과제"],
    "life": ["생활", "지각", "복장", "친구", "태도"],
}


@dataclass
class ClassificationResult:
    category: str
    confidence: float
    model_name: str
    reason: str = ""


def classify(text: str) -> ClassificationResult:
    data = call_claude_json(
        system=SYSTEM_PROMPT,
        user_content=text,
        model=settings.ai_classify_model,
        max_tokens=256,
        caller="F1.classifier",
    )
    if data is None:
        return _fallback(text)

    category = data.get("category", "other")
    if category not in CATEGORIES:
        category = "other"
    try:
        return ClassificationResult(
            category=category,
            confidence=float(data.get("confidence", 0.5)),
            model_name=settings.ai_classify_model,
            reason=str(data.get("reason", "")),
        )
    except (TypeError, ValueError):
        # confidence 필드가 숫자가 아닌 등 응답 스키마 위반 — fallback으로.
        return _fallback(text)


def _fallback(text: str) -> ClassificationResult:
    for category, words in _KEYWORDS.items():
        if any(w in text for w in words):
            return ClassificationResult(category, 0.4, "keyword-fallback", "키워드 규칙 매칭")
    return ClassificationResult("other", 0.3, "keyword-fallback", "매칭 없음")
