"""Anthropic 클라이언트 래퍼 + 공통 호출 레이어 (AI 서빙).

F1(classifier)·F2(risk)·F4(drafter)가 전부 이 파일의 call_claude() /
call_claude_json()을 거친다. 개별 서비스는 API 키 유무·타임아웃·재시도·
로깅을 각자 신경 쓸 필요 없이, "성공하면 결과, 실패하면 None"만 받아서
자기 fallback 로직으로 넘기면 된다.

설계 원칙: 이 레이어는 실패를 감추지 않는다. 실패하면 표준화된 형식으로
로깅하고 None을 반환할 뿐이며, 무엇을 fallback으로 쓸지는 항상 호출부가
정한다(F1은 키워드 규칙, F4는 정형 문구 등 — 도메인마다 다르므로).
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

try:
    import anthropic
    from anthropic import Anthropic
except ImportError:  # 의존성 미설치 환경 방어
    anthropic = None  # type: ignore
    Anthropic = None  # type: ignore


@lru_cache
def get_anthropic() -> "Anthropic | None":
    """키가 없거나 SDK 미설치면 None — 상위 서비스가 fallback 하도록.

    타임아웃·재시도는 SDK 자체 기능에 위임한다(요청당 타임아웃, 5xx·429·
    네트워크 오류에 대한 지수 백오프 재시도). 재시도 횟수를 너무 크게
    잡으면 사용자 응답 경로(F1·F2)가 오래 막히므로 설정값으로 노출해
    운영 중 조정 가능하게 한다.
    """
    if Anthropic is None or not settings.anthropic_api_key:
        return None
    return Anthropic(
        api_key=settings.anthropic_api_key,
        timeout=settings.ai_timeout_seconds,
        max_retries=settings.ai_max_retries,
    )


@dataclass
class ClaudeCallResult:
    text: str
    model: str
    latency_ms: int


def call_claude(
    *,
    system: str,
    user_content: str,
    model: str,
    max_tokens: int,
    caller: str,
) -> ClaudeCallResult | None:
    """공통 Claude 호출 창구. 실패해도 예외를 던지지 않고 None을 반환한다.

    caller: 로그에서 어느 서비스(F1/F2/F4)의 호출인지 구분하기 위한 태그.
    예: "F1.classifier", "F2.risk", "F4.drafter".
    """
    client = get_anthropic()
    if client is None:
        logger.info("ai_serving | %s: API 키 없음 → fallback", caller)
        return None

    started = time.monotonic()
    try:
        msg = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user_content}],
        )
    except anthropic.RateLimitError as e:
        # SDK가 이미 max_retries만큼 자체 재시도(429 포함)한 뒤에도 실패한
        # 경우에만 여기로 온다 — 사용자를 더 기다리게 하지 않고 바로 fallback.
        logger.warning("ai_serving | %s: rate limited → fallback: %s", caller, e)
        return None
    except anthropic.APITimeoutError as e:
        logger.warning(
            "ai_serving | %s: 타임아웃(%.0fs) → fallback: %s",
            caller, settings.ai_timeout_seconds, e,
        )
        return None
    except anthropic.APIConnectionError as e:
        logger.warning("ai_serving | %s: 연결 실패 → fallback: %s", caller, e)
        return None
    except anthropic.APIError as e:
        # 4xx(요청 자체 문제 등) 포함 — 재시도해도 똑같이 실패할 가능성이
        # 높은 나머지 API 오류. 재시도하지 않고 바로 fallback.
        logger.error("ai_serving | %s: API 오류 → fallback: %s", caller, e)
        return None
    except Exception:  # 예상 못한 오류로 서비스 전체가 죽지 않게 하는 마지막 방어선
        logger.exception("ai_serving | %s: 예상치 못한 오류 → fallback", caller)
        return None

    latency_ms = int((time.monotonic() - started) * 1000)
    try:
        text = msg.content[0].text  # type: ignore[attr-defined]
    except (IndexError, AttributeError):
        logger.error("ai_serving | %s: 응답 형식이 예상과 다름 → fallback", caller)
        return None

    logger.info("ai_serving | %s: model=%s latency_ms=%d", caller, model, latency_ms)
    return ClaudeCallResult(text=text, model=model, latency_ms=latency_ms)


def call_claude_json(
    *,
    system: str,
    user_content: str,
    model: str,
    max_tokens: int,
    caller: str,
) -> dict[str, Any] | None:
    """JSON 응답을 기대하는 호출(F1 분류·F2 위험도)의 공통 래퍼.

    호출 자체가 실패했거나, 응답은 왔는데 JSON 파싱이 안 되면 둘 다 None —
    호출부 입장에서는 "성공(dict) / 실패(None)" 두 가지만 처리하면 된다.
    """
    result = call_claude(
        system=system,
        user_content=user_content,
        model=model,
        max_tokens=max_tokens,
        caller=caller,
    )
    if result is None:
        return None
    try:
        return json.loads(_strip_markdown_fence(result.text))
    except json.JSONDecodeError:
        logger.error(
            "ai_serving | %s: JSON 파싱 실패(원문 앞 200자): %r",
            caller, result.text[:200],
        )
        return None


def _strip_markdown_fence(text: str) -> str:
    """"JSON만 출력하라"고 프롬프트에 명시해도 모델이 ```json ... ``` 로
    감싸서 답하는 경우가 실제로 흔하다(특히 짧은 모델일수록). 이 경우
    json.loads가 실패해서 API 호출은 성공했는데도 불필요하게 fallback으로
    떨어지므로, 파싱 전에 감싸는 코드펜스만 제거한다.
    """
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        # 첫 줄(```json 또는 ```)과 마지막 줄(```) 제거
        if lines and lines[-1].strip() == "```":
            lines = lines[1:-1]
        else:
            lines = lines[1:]
        stripped = "\n".join(lines).strip()
    return stripped
