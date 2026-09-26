"""AI 서빙 공통 레이어의 응답 파싱 테스트.

`content[0]` 을 그대로 집으면 모델에 따라 깨진다. Claude Sonnet 5 는 thinking 이
기본으로 켜져 있어 응답의 첫 블록이 thinking(`text=None`)이고, 실제 답변은 그다음
블록에 있다. Haiku 4.5 는 thinking 이 꺼져 있어 첫 블록이 곧 텍스트다.

그래서 **F1·F2(Haiku)는 멀쩡한데 F4(Sonnet)만 500 으로 죽는** 모양이 됐다 —
초안이 None 으로 저장되다 `answer_drafts.draft_body` NOT NULL 에 걸렸다.

실제 API 를 호출하지 않는다. 응답 객체만 흉내 내어 파싱 규칙을 고정한다.
"""

from types import SimpleNamespace

import pytest

from app.services.ai.client import _first_text


def block(type_: str, **fields):
    return SimpleNamespace(type=type_, **fields)


def msg(*blocks):
    return SimpleNamespace(content=list(blocks))


# --- 정상 ------------------------------------------------------------------


def test_텍스트_블록_하나():
    assert _first_text(msg(block("text", text="답변"))) == "답변"


def test_thinking_이_먼저_와도_텍스트를_찾는다():
    """Claude Sonnet 5 의 실제 응답 모양 — 이 케이스가 500 을 냈다."""
    response = msg(block("thinking", text=None, thinking=""), block("text", text="실제 답변"))
    assert _first_text(response) == "실제 답변"


def test_텍스트가_여러_개면_첫_번째():
    response = msg(block("text", text="첫째"), block("text", text="둘째"))
    assert _first_text(response) == "첫째"


def test_알_수_없는_블록이_섞여도_통과():
    response = msg(block("tool_use", input={}), block("text", text="답변"))
    assert _first_text(response) == "답변"


# --- 실패로 처리해야 하는 경우 ----------------------------------------------


def test_텍스트_블록이_없으면_None():
    assert _first_text(msg(block("thinking", text=None, thinking=""))) is None


def test_빈_응답은_None():
    assert _first_text(msg()) is None


@pytest.mark.parametrize("empty", ["", None])
def test_텍스트가_비어_있으면_None(empty):
    """빈 초안을 저장하느니 정형 문구로 떨어지는 편이 낫다."""
    assert _first_text(msg(block("text", text=empty))) is None


def test_content_가_없어도_터지지_않는다():
    assert _first_text(SimpleNamespace()) is None
    assert _first_text(SimpleNamespace(content=None)) is None


def test_빈_텍스트_뒤의_실제_텍스트를_찾는다():
    response = msg(block("text", text=""), block("text", text="진짜 답변"))
    assert _first_text(response) == "진짜 답변"
