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
