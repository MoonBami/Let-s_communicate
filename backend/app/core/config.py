from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "development"
    secret_key: str = "change-me"
    access_token_expire_minutes: int = 1440
    algorithm: str = "HS256"

    cors_origins: str = "http://localhost:5173"

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/sotonghaeyo"
    redis_url: str = "redis://localhost:6379/0"

    anthropic_api_key: str | None = None
    ai_classify_model: str = "claude-haiku-4-5-20251001"
    ai_draft_model: str = "claude-sonnet-5"

    # 자동 응대 게이트 — 이 신뢰도 미만이면 챗봇에 맡기지 않고 교사에게 보낸다.
    # 오분류 비용이 비대칭이므로(§services/ai/gate.py) 기본값을 높게 잡는다.
    # 참고: 규칙 기반 fallback 분류기는 신뢰도 0.4 를 반환하므로 이 기본값에서는
    # 자동 응대가 발생하지 않는다 — 키워드 매칭만으로 자동 응대하지 않겠다는 뜻.
    auto_answer_min_confidence: float = 0.7

    # F5 임베딩 — OpenAI 호환 /v1/embeddings. 키가 없으면 해싱 fallback.
    embedding_api_key: str | None = None
    embedding_api_url: str = "https://api.openai.com/v1/embeddings"
    embedding_model: str = "text-embedding-3-small"

    # F7 STT — CLOVA Speech Long Sentence. 미설정이면 변환 태스크가 실패한다.
    clova_stt_url: str | None = None
    clova_stt_secret: str | None = None

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
