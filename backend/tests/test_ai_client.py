"""AI 서빙 공통 레이어(services/ai/client.py) 테스트.

실제 Anthropic API 키 없이도 도는 순수 로직 테스트다 — 네트워크 호출은
전부 unittest.mock으로 흉내낸다. 여기서 검증하는 건 "Claude API가 이렇게
실패했을 때, 우리 코드가 예외를 흘리지 않고 정확히 None을 반환하는가"다.

실제 키로만 확인 가능한 것(모델명 유효성, 실제 응답 품질 등)은 여기서
검증 범위 밖이다 — PR 설명의 "실제 키 테스트 체크리스트" 참고.
"""

import json

import anthropic
import httpx
import pytest

from app.services.ai import client as ai_client


@pytest.fixture(autouse=True)
def _clear_client_cache():
    """get_anthropic()은 lru_cache라, 테스트마다 설정을 바꿔가며 검증하려면
    캐시를 매번 비워야 한다. 안 비우면 첫 테스트에서 만들어진 클라이언트가
    이후 테스트에도 그대로 재사용돼 assert가 틀어진다."""
    ai_client.get_anthropic.cache_clear()
    yield
    ai_client.get_anthropic.cache_clear()


@pytest.fixture
def fake_settings(monkeypatch):
    """키가 있는 것처럼 흉내내는 설정. 개별 테스트에서 timeout 등을
    바꾸고 싶으면 반환된 settings 객체를 추가로 monkeypatch하면 된다."""
    monkeypatch.setattr(ai_client.settings, "anthropic_api_key", "fake-test-key")
    monkeypatch.setattr(ai_client.settings, "ai_timeout_seconds", 20.0)
    monkeypatch.setattr(ai_client.settings, "ai_max_retries", 2)
    return ai_client.settings


class TestGetAnthropic:
    def test_returns_none_without_api_key(self, monkeypatch):
        monkeypatch.setattr(ai_client.settings, "anthropic_api_key", None)
        assert ai_client.get_anthropic() is None

    def test_returns_client_with_api_key(self, fake_settings):
        result = ai_client.get_anthropic()
        assert result is not None


class TestCallClaude:
    """call_claude()가 각 실패 유형을 예외로 흘리지 않고 None으로
    흡수하는지 확인한다 — 이게 F4(drafter)에서 실제로 빠져있던 버그다."""

    def _patch_create(self, monkeypatch, fake_settings, side_effect=None, return_value=None):
        client = ai_client.get_anthropic()
        if side_effect is not None:
            monkeypatch.setattr(client.messages, "create", lambda **kw: (_ for _ in ()).throw(side_effect))
        else:
            monkeypatch.setattr(client.messages, "create", lambda **kw: return_value)
        return client

    def test_success_returns_result(self, monkeypatch, fake_settings):
        fake_msg = type("M", (), {"content": [type("C", (), {"text": "hello", "type": "text"})()]})()
        self._patch_create(monkeypatch, fake_settings, return_value=fake_msg)

        result = ai_client.call_claude(
            system="sys", user_content="hi", model="claude-haiku-4-5-20251001",
            max_tokens=100, caller="test.success",
        )
        assert result is not None
        assert result.text == "hello"
        assert result.model == "claude-haiku-4-5-20251001"
        assert result.latency_ms >= 0

    def test_no_api_key_returns_none(self, monkeypatch):
        monkeypatch.setattr(ai_client.settings, "anthropic_api_key", None)
        result = ai_client.call_claude(
            system="sys", user_content="hi", model="m", max_tokens=10, caller="test.nokey",
        )
        assert result is None

    def test_timeout_returns_none_not_raises(self, monkeypatch, fake_settings):
        # 이 케이스가 F4(drafter)에서 실제로 터졌던 버그를 재현한 것.
        # 예전 drafter.py는 이 예외를 그대로 던져서 500 에러가 났다.
        self._patch_create(
            monkeypatch, fake_settings,
            side_effect=anthropic.APITimeoutError(request=None),
        )
        result = ai_client.call_claude(
            system="sys", user_content="hi", model="m", max_tokens=10, caller="test.timeout",
        )
        assert result is None

    def test_rate_limit_returns_none_not_raises(self, monkeypatch, fake_settings):
        request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        response = httpx.Response(status_code=429, request=request)
        self._patch_create(
            monkeypatch, fake_settings,
            side_effect=anthropic.RateLimitError(
                message="rate limited", response=response, body=None,
            ),
        )
        result = ai_client.call_claude(
            system="sys", user_content="hi", model="m", max_tokens=10, caller="test.ratelimit",
        )
        assert result is None

    def test_connection_error_returns_none_not_raises(self, monkeypatch, fake_settings):
        self._patch_create(
            monkeypatch, fake_settings,
            side_effect=anthropic.APIConnectionError(request=None),
        )
        result = ai_client.call_claude(
            system="sys", user_content="hi", model="m", max_tokens=10, caller="test.connerr",
        )
        assert result is None

    def test_unexpected_exception_returns_none_not_raises(self, monkeypatch, fake_settings):
        # SDK가 어떤 새 예외 타입을 던지든, 서비스 전체가 죽으면 안 된다는
        # 마지막 방어선(bare except) 검증.
        self._patch_create(monkeypatch, fake_settings, side_effect=RuntimeError("무언가 예상 못한 오류"))
        result = ai_client.call_claude(
            system="sys", user_content="hi", model="m", max_tokens=10, caller="test.unexpected",
        )
        assert result is None

    def test_malformed_response_shape_returns_none(self, monkeypatch, fake_settings):
        """content가 빈 리스트인 등 응답 구조 자체가 예상과 다른 경우도
        방어되어야 한다(운영 중 SDK/모델 쪽 변화로 실제 발생 가능한 케이스)."""
        fake_msg = type("M", (), {"content": []})()
        self._patch_create(monkeypatch, fake_settings, return_value=fake_msg)

        result = ai_client.call_claude(
            system="sys", user_content="hi", model="m", max_tokens=10, caller="test.malformed",
        )
        assert result is None

    def test_extended_thinking_block_before_text_block(self, monkeypatch, fake_settings):
        """실제 운영 중 재현된 버그의 회귀 테스트.

        claude-sonnet-5처럼 확장 추론을 쓰는 모델은 content[0]이 text가 아닌
        thinking 블록일 수 있다. 예전 코드는 content[0].text를 무조건
        가져다 썼는데, 이 경우 .text 속성은 존재하되 값이 None이라 예외 없이
        조용히 통과해버렸고, F4(drafter)에서 draft_body가 None인 채로 DB에
        저장되려다 NOT NULL 제약 위반으로 500 에러가 났다(실제 프로덕션에서
        발생, F1/F2는 다른 모델을 써서 우연히 안 드러남).
        """
        thinking_block = type("Thinking", (), {"type": "thinking", "text": None, "thinking": "추론 중..."})()
        text_block = type("Text", (), {"type": "text", "text": "실제 답변 내용입니다."})()
        fake_msg = type("M", (), {"content": [thinking_block, text_block]})()
        self._patch_create(monkeypatch, fake_settings, return_value=fake_msg)

        result = ai_client.call_claude(
            system="sys", user_content="hi", model="claude-sonnet-5", max_tokens=10,
            caller="test.thinking",
        )
        assert result is not None
        assert result.text == "실제 답변 내용입니다."


class TestCallClaudeJson:
    def _patch_create(self, monkeypatch, fake_settings, text):
        client = ai_client.get_anthropic()
        fake_msg = type("M", (), {"content": [type("C", (), {"text": text, "type": "text"})()]})()
        monkeypatch.setattr(client.messages, "create", lambda **kw: fake_msg)

    def test_parses_plain_json(self, monkeypatch, fake_settings):
        self._patch_create(monkeypatch, fake_settings, '{"category": "grades", "confidence": 0.9}')
        data = ai_client.call_claude_json(
            system="s", user_content="u", model="m", max_tokens=10, caller="test.plain",
        )
        assert data == {"category": "grades", "confidence": 0.9}

    def test_strips_markdown_json_fence(self, monkeypatch, fake_settings):
        # 실제로 흔히 벌어지는 케이스 — "JSON만 출력하라"고 해도 모델이
        # ```json ... ``` 로 감싸서 답하는 경우.
        self._patch_create(monkeypatch, fake_settings, '```json\n{"a": 1}\n```')
        data = ai_client.call_claude_json(
            system="s", user_content="u", model="m", max_tokens=10, caller="test.fenced",
        )
        assert data == {"a": 1}

    def test_strips_plain_code_fence_without_language_tag(self, monkeypatch, fake_settings):
        self._patch_create(monkeypatch, fake_settings, '```\n{"a": 1}\n```')
        data = ai_client.call_claude_json(
            system="s", user_content="u", model="m", max_tokens=10, caller="test.fenced2",
        )
        assert data == {"a": 1}

    def test_invalid_json_returns_none(self, monkeypatch, fake_settings):
        self._patch_create(monkeypatch, fake_settings, "이건 JSON이 아닙니다")
        data = ai_client.call_claude_json(
            system="s", user_content="u", model="m", max_tokens=10, caller="test.invalid",
        )
        assert data is None

    def test_upstream_failure_returns_none(self, monkeypatch, fake_settings):
        client = ai_client.get_anthropic()
        monkeypatch.setattr(
            client.messages, "create",
            lambda **kw: (_ for _ in ()).throw(anthropic.APITimeoutError(request=None)),
        )
        data = ai_client.call_claude_json(
            system="s", user_content="u", model="m", max_tokens=10, caller="test.upstreamfail",
        )
        assert data is None


class TestStripMarkdownFence:
    """파싱 이전 단계 유틸리티 자체를 직접 검증 — call_claude_json을
    거치지 않고 경계 케이스를 더 촘촘히 본다."""

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ('{"a": 1}', '{"a": 1}'),
            ('```json\n{"a": 1}\n```', '{"a": 1}'),
            ('```\n{"a": 1}\n```', '{"a": 1}'),
            ('  {"a": 1}  ', '{"a": 1}'),
        ],
    )
    def test_strip_variants(self, raw, expected):
        assert ai_client._strip_markdown_fence(raw) == expected

    def test_no_fence_returns_unchanged_content(self):
        text = '{"category": "life"}'
        assert json.loads(ai_client._strip_markdown_fence(text)) == {"category": "life"}
