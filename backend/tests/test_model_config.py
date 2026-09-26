"""AI 모델 설정 검증.

모델 ID 를 잘못 쓰면 **아무 오류도 보이지 않는다.** 호출이 404 로 실패하고
`services/ai/client.py` 가 예외를 잡아 fallback 으로 떨어지기 때문이다. 키를 넣었는데
AI 가 안 도는데 로그를 뒤지기 전엔 알 수 없는 상태가 된다.

실제로 `claude-haiku-4-5-20251001` 처럼 날짜 접미사가 붙어 있었다. 모델 ID 는
접미사 없는 정확한 문자열을 써야 한다.

DB·네트워크 없이 도는 설정 검사다.
"""

import re

import pytest

from app.core.config import settings

# 날짜 접미사 패턴 — 끝에 -YYYYMMDD 또는 @YYYYMMDD 가 붙은 형태.
_DATE_SUFFIX = re.compile(r"[-@]\d{8}$")

MODEL_SETTINGS = ["ai_classify_model", "ai_draft_model"]


@pytest.mark.parametrize("name", MODEL_SETTINGS)
def test_모델_ID_에_날짜_접미사가_없다(name):
    value = getattr(settings, name)
    assert not _DATE_SUFFIX.search(value), (
        f"{name}={value!r} 에 날짜 접미사가 붙었다. 호출이 404 로 실패하고 "
        "조용히 fallback 으로 떨어져 '키를 넣었는데 AI 가 안 도는' 상태가 된다."
    )


@pytest.mark.parametrize("name", MODEL_SETTINGS)
def test_모델_ID_형식(name):
    value = getattr(settings, name)
    assert value.startswith("claude-"), f"{name}={value!r}"
    assert value == value.strip(), "앞뒤 공백이 있으면 그대로 요청에 실린다"
    assert " " not in value


def test_분류와_초안_모델이_각각_지정되어_있다():
    """F1·F2 는 빠른 모델, F4 는 문장 품질이 중요한 모델로 나눠 쓴다."""
    assert settings.ai_classify_model
    assert settings.ai_draft_model


def test_env_example_의_모델_ID_도_같은_규칙을_지킨다():
    """`.env.example` 을 복사해 쓰므로 여기가 틀리면 그대로 전파된다."""
    from pathlib import Path

    env_example = Path(__file__).resolve().parents[1] / ".env.example"
    for line in env_example.read_text(encoding="utf-8").splitlines():
        if line.startswith(("AI_CLASSIFY_MODEL=", "AI_DRAFT_MODEL=")):
            value = line.split("=", 1)[1].strip()
            assert not _DATE_SUFFIX.search(value), f".env.example: {line}"
