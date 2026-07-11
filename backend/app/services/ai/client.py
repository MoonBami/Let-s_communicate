"""Anthropic 클라이언트 래퍼.

API 키가 없으면 None을 반환하여 상위 서비스가 '규칙 기반 fallback'으로
동작하도록 한다(로컬 개발·데모에서 키 없이도 앱이 뜨도록).
"""

from functools import lru_cache

from app.core.config import settings

try:
    from anthropic import Anthropic
except ImportError:  # 의존성 미설치 환경 방어
    Anthropic = None  # type: ignore


@lru_cache
def get_anthropic() -> "Anthropic | None":
    if Anthropic is None or not settings.anthropic_api_key:
        return None
    return Anthropic(api_key=settings.anthropic_api_key)
