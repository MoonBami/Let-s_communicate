"""DATABASE_URL 드라이버 정규화.

Vercel–Neon 연동이 주입하는 `postgres://`·`postgresql://` 를 그대로 쓰면 SQLAlchemy 가
psycopg2 를 찾다가 앱 import 단계에서 죽는다(배포 전체가 FUNCTION_INVOCATION_FAILED).
설치된 드라이버는 psycopg(v3)뿐이므로 설정에서 접두사를 맞춘다.

DB·네트워크 없이 도는 설정 검사다.
"""

import pytest
from sqlalchemy import create_engine

from app.core.config import Settings

NEON = "user:pw@ep-x-pooler.ap-northeast-1.aws.neon.tech/neondb?sslmode=require"


@pytest.mark.parametrize("scheme", ["postgres://", "postgresql://", "postgresql+psycopg://"])
def test_어떤_접두사든_psycopg_드라이버로_맞춘다(scheme):
    url = Settings(database_url=scheme + NEON).database_url
    assert url == "postgresql+psycopg://" + NEON


def test_정규화한_주소로_엔진을_만들_수_있다():
    # create_engine 은 접속하지 않고 방언·드라이버만 불러온다 — import 단계 실패 재현용.
    engine = create_engine(Settings(database_url="postgres://" + NEON).database_url)
    assert engine.dialect.driver == "psycopg"
