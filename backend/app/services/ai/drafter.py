"""F4: 공식 답변 초안 생성.

민원 원문 + (선택)학교 규정/톤 가이드를 넣어 정중한 답변 초안을 생성.
RAG(F5)로 유사 사례를 붙이면 품질이 올라감 — 지금은 인터페이스만.
"""

from app.core.config import settings
from app.services.ai.client import get_anthropic

SYSTEM_PROMPT = """너는 학교 교사의 민원 답변 초안을 작성하는 보조 시스템이다.
규칙:
- 정중하고 공식적인 존댓말.
- 사실관계 단정 금지. 확인이 필요한 부분은 '확인 후 안내드리겠습니다'로.
- 3~6문장. 학부모를 존중하는 톤.
- 초안일 뿐이며 교사가 최종 검토·수정한다는 것을 전제.
"""


def draft_answer(complaint_body: str, similar_cases: list[str] | None = None) -> tuple[str, str]:
    """returns (draft_body, model_name)"""
    client = get_anthropic()
    if client is None:
        return (
            "안녕하세요, 학부모님. 남겨주신 내용을 잘 확인하였습니다. "
            "관련 사항을 확인한 뒤 정확한 내용으로 다시 안내드리겠습니다. "
            "불편을 드려 죄송하며, 빠르게 살펴보겠습니다. 감사합니다.",
            "template-fallback",
        )

    context = ""
    if similar_cases:
        joined = "\n- ".join(similar_cases)
        context = f"\n\n[참고 유사 사례]\n- {joined}"

    msg = client.messages.create(
        model=settings.ai_draft_model,
        max_tokens=600,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"[민원 내용]\n{complaint_body}{context}"}],
    )
    return msg.content[0].text, settings.ai_draft_model  # type: ignore[attr-defined]
