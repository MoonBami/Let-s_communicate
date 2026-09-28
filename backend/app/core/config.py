from functools import lru_cache

from pydantic import field_validator
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
    # 모델 ID 에 날짜 접미사를 붙이지 않는다. "claude-haiku-4-5-20251001" 처럼 쓰면
    # 404 가 나고, client.py 가 예외를 잡아 조용히 fallback 으로 떨어진다 —
    # 키를 넣어도 AI 가 안 도는데 오류도 안 보이는 상태가 된다.
    ai_classify_model: str = "claude-haiku-4-5"   # F1 분류·F2 위험 (빠르고 저렴)
    ai_draft_model: str = "claude-sonnet-5"       # F4 답변 초안 (문장 품질 우선)
    # AI 서빙 공통 레이어(services/ai/client.py) 타임아웃·재시도 설정.
    # F1·F2는 사용자 응답 경로(민원 접수)에 있으므로 너무 길게 잡지 않는다 —
    # 넘기면 예외 없이 fallback으로 떨어진다.
    ai_timeout_seconds: float = 20.0
    ai_max_retries: int = 2

    # 자동 응대 게이트 — 이 신뢰도 미만이면 챗봇에 맡기지 않고 교사에게 보낸다.
    # 오분류 비용이 비대칭이므로(§services/ai/gate.py) 기본값을 높게 잡는다.
    # 참고: 규칙 기반 fallback 분류기는 신뢰도 0.4 를 반환하므로 이 기본값에서는
    # 자동 응대가 발생하지 않는다 — 키워드 매칭만으로 자동 응대하지 않겠다는 뜻.
    auto_answer_min_confidence: float = 0.7

    # 민원 접수 유량 제한 (services/../core/rate_limit.py)
    # 분당 한도는 '사람이 넘길 수 없는 수준'으로만 잡아 스크립트를 걸러낸다.
    # 시간당 한도를 크게 둔 이유: 익명 접수는 IP 로 세는데, 같은 학교 와이파이·
    # 통신사 NAT 뒤의 학부모들이 IP 를 공유한다. 사건이 터져 여러 학부모가 동시에
    # 민원을 넣을 때 정당한 민원이 서로를 막으면 안 된다.
    rate_limit_intake_per_minute: int = 5
    rate_limit_intake_per_hour: int = 100

    # 학교 코드 조회 유량 제한. 학교 정보는 공개라 막을 것은 '코드 전수 대입으로
    # 이 서비스를 쓰는 학교 목록을 긁어가는 것' 정도다. 학부모는 코드를 한두 번
    # 확인할 뿐이므로 분당 30회면 NAT 를 공유해도 넉넉하다.
    rate_limit_school_lookup_per_minute: int = 30

    # 프록시(로드밸런서·리버스 프록시) 뒤에 있을 때만 켠다.
    # 켜면 X-Forwarded-For 를 클라이언트 IP 로 신뢰한다 — 프록시가 없는데 켜면
    # 공격자가 헤더를 위조해 한도를 무한히 우회할 수 있으므로 기본값은 꺼둔다.
    trust_proxy_headers: bool = False

    # F5 임베딩 — OpenAI 호환 /v1/embeddings. 키가 없으면 해싱 fallback.
    embedding_api_key: str | None = None
    embedding_api_url: str = "https://api.openai.com/v1/embeddings"
    embedding_model: str = "text-embedding-3-small"

    # F7 STT — CLOVA Speech Long Sentence. 미설정이면 변환 태스크가 실패한다.
    clova_stt_url: str | None = None
    clova_stt_secret: str | None = None

    @field_validator("database_url")
    @classmethod
    def _use_psycopg_driver(cls, v: str) -> str:
        """드라이버를 psycopg(v3)로 고정한다.

        Vercel–Neon 연동은 `DATABASE_URL` 을 `postgres://`·`postgresql://` 로 주입하고,
        연동이 다시 동기화되면 손으로 고친 값을 덮어쓴다. 그대로 두면 SQLAlchemy 가
        설치되지 않은 psycopg2 를 찾거나(`postgresql://`) 방언을 못 찾아(`postgres://`)
        **앱 import 단계에서 죽는다** — /health 까지 전부 500 이 된다.
        """
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+psycopg://" + v[len(prefix):]
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
