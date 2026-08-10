"""F1: 민원 자동 분류.

핵심: '모델을 직접 학습'하는 게 아니라, LLM에 few-shot 프롬프트를 주고
JSON을 받아 파싱하는 방식. 키가 없으면 키워드 규칙 기반 fallback.
데이터가 쌓이면 이 인터페이스를 유지한 채 KoELECTRA 등으로 교체 가능.
"""

import json
from dataclasses import dataclass

from app.core.config import settings
from app.services.ai.client import get_anthropic

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

# 학교폭력·분쟁 신호. gate.py 의 '자동 응대 금지' 판정도 이 목록을 공유한다
# (같은 신호를 두 곳에서 따로 관리하면 한쪽만 갱신되는 사고가 난다).
VIOLENCE_KEYWORDS = ["폭력", "때리", "괴롭", "학폭", "협박", "싸움"]

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
    client = get_anthropic()
    if client is None:
        return _fallback(text)

    try:
        msg = client.messages.create(
            model=settings.ai_classify_model,
            max_tokens=256,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": text}],
        )
        raw = msg.content[0].text  # type: ignore[attr-defined]
        data = json.loads(raw)
        category = data.get("category", "other")
        if category not in CATEGORIES:
            category = "other"
        return ClassificationResult(
            category=category,
            confidence=float(data.get("confidence", 0.5)),
            model_name=settings.ai_classify_model,
            reason=data.get("reason", ""),
        )
    except Exception:
        # 파싱/네트워크 실패 시에도 서비스가 죽지 않도록 fallback
        return _fallback(text)


def _fallback(text: str) -> ClassificationResult:
    for category, words in _KEYWORDS.items():
        if any(w in text for w in words):
            return ClassificationResult(category, 0.4, "keyword-fallback", "키워드 규칙 매칭")
    return ClassificationResult("other", 0.3, "keyword-fallback", "매칭 없음")
