"""라우트 테스트용 공용 픽스처 (실제 PostgreSQL + TestClient).

## 왜 진짜 DB 를 쓰는가

스키마가 PostgreSQL 전용 기능에 의존한다 — 네이티브 ENUM(`complaint_status` 등),
`JSONB`, `UUID`, pgvector `VECTOR(1536)`. SQLite 로 대체하면 **프로덕션과 다른
것을 검증**하게 되고, 정작 문제가 생기는 지점(ENUM 값 불일치, 권한 쿼리)을 놓친다.

## 왜 별도 스위트인가

기존 단위 테스트는 DB·네트워크 없이 1초 안에 돌고 CI 에서 매번 실행된다.
그 성질을 잃지 않도록 DB 가 필요한 테스트만 `@pytest.mark.api` 로 묶고,
DB 에 붙지 못하면 **이유를 밝히고 건너뛴다.** 조용히 통과하지 않는다.

    pytest                 # 전부 (DB 없으면 api 마크는 skip)
    pytest -m "not api"    # 단위 테스트만
    pytest -m api          # 라우트 테스트만

## 테스트 DB 지정

`TEST_DATABASE_URL` 이 있으면 그것을, 없으면 `DATABASE_URL` 의 DB 이름 뒤에
`_test` 를 붙여 쓴다. **DB 이름이 `_test` 로 끝나지 않으면 실행을 거부한다** —
이 파일은 매 테스트마다 테이블을 비우므로 개발 DB 를 가리키면 데이터가 날아간다.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.security import create_access_token, hash_password

SCHEMA_SQL = Path(__file__).resolve().parents[2] / "db" / "schema.sql"

SCHOOL_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
STUDENT_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")

TEST_PASSWORD = "test1234"

# bcrypt 는 의도적으로 느리다(계정당 ~0.25초). 테스트마다 4개 계정을 만들면
# 그것만으로 스위트가 몇 배 느려지므로 해시를 한 번만 계산해 재사용한다.
# 로그인 검증은 같은 해시로 그대로 동작한다.
_password_hash: str | None = None


def _cached_password_hash() -> str:
    global _password_hash
    if _password_hash is None:
        _password_hash = hash_password(TEST_PASSWORD)
    return _password_hash


def _test_database_url() -> str:
    explicit = os.getenv("TEST_DATABASE_URL")
    if explicit:
        return explicit
    base = settings.database_url
    # 마지막 경로 조각(DB 이름)에만 _test 를 붙인다.
    head, _, name = base.rpartition("/")
    return f"{head}/{name}_test"


def _guard_not_dev_db(url: str) -> None:
    name = url.rpartition("/")[2].split("?")[0]
    if not name.endswith("_test"):
        pytest.fail(
            f"테스트 DB 이름이 '_test' 로 끝나지 않는다: {name!r}. "
            "이 스위트는 매 테스트마다 테이블을 비우므로 개발 DB 를 가리키면 안 된다."
        )


@pytest.fixture(scope="session")
def engine():
    """테스트 DB 엔진. 붙지 못하면 이유를 밝히고 스위트를 건너뛴다."""
    url = _test_database_url()
    _guard_not_dev_db(url)

    eng = create_engine(url, pool_pre_ping=True, future=True)
    try:
        with eng.connect() as conn:
            conn.execute(text("select 1"))
    except Exception as exc:
        pytest.skip(
            f"테스트 DB 에 붙지 못해 라우트 테스트를 건너뛴다 ({url}): {exc}\n"
            "  띄우려면: docker run -d --name sotong-test-db -e POSTGRES_PASSWORD=postgres "
            "-e POSTGRES_DB=sotonghaeyo_test -p 5433:5432 pgvector/pgvector:pg16\n"
            "  그리고: TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5433/sotonghaeyo_test",
            allow_module_level=True,
        )

    # 매 세션 처음에 스키마를 새로 만든다(이전 실행 잔재 제거).
    ddl = SCHEMA_SQL.read_text(encoding="utf-8")
    with eng.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    with eng.begin() as conn:
        conn.exec_driver_sql(ddl)

    yield eng
    eng.dispose()


@pytest.fixture(autouse=True)
def _isolate_rate_limit(monkeypatch):
    """유량 제한을 테스트 간에 격리한다.

    카운터는 프로세스 전역이라 초기화하지 않으면 **앞 테스트의 접수 횟수가 누적**되어
    뒤 테스트가 429 를 받는다. 실제로 그랬다 — 유량 제한과 라우트 테스트가 각각
    따로는 통과하는데 함께 돌리면 10건이 깨졌다.

    Redis 도 쓰지 않도록 고정한다. 환경에 Redis 가 떠 있으면 카운터가 테스트
    실행 사이에도 남아 결과가 환경에 따라 달라지기 때문이다.
    """
    from app.core import rate_limit

    monkeypatch.setattr(rate_limit, "_redis_counter", None)
    monkeypatch.setattr(rate_limit, "_redis_checked", True)
    rate_limit.reset_for_tests()
    yield
    rate_limit.reset_for_tests()


@pytest.fixture()
def db(engine) -> Session:
    """테스트 1건용 세션. 시작 전에 모든 테이블을 비운다.

    앱 코드가 내부에서 commit 하므로(접수 파이프라인) 롤백 대신 절단으로
    격리한다 — 앱의 커밋 동작을 그대로 두고 검증하기 위해서다.
    """
    with engine.begin() as conn:
        tables = conn.execute(
            text(
                "select tablename from pg_tables where schemaname='public'"
            )
        ).scalars().all()
        if tables:
            joined = ", ".join(f'"{t}"' for t in tables)
            conn.execute(text(f"TRUNCATE {joined} RESTART IDENTITY CASCADE"))

    maker = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = maker()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(engine, db):
    """앱의 get_db 를 테스트 DB 로 갈아끼운 TestClient."""
    from fastapi.testclient import TestClient

    from app.db.session import get_db
    from app.main import app

    maker = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    def _override():
        session = maker()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# --- 도메인 픽스처 ----------------------------------------------------------


@pytest.fixture()
def school(db):
    from app.models.user import School

    row = School(id=SCHOOL_ID, name="테스트 초등학교")
    db.add(row)
    db.commit()
    return row


@pytest.fixture()
def student(db, school):
    from app.models.user import Student

    row = Student(id=STUDENT_ID, school_id=SCHOOL_ID, name="김학생", grade=3, class_name="2")
    db.add(row)
    db.commit()
    return row


@pytest.fixture()
def users(db, school):
    """역할별 계정 4종. `users["teacher"]` 처럼 쓴다."""
    from app.models.user import User

    made = {}
    for role in ("teacher", "parent", "admin", "mdt"):
        user = User(
            school_id=SCHOOL_ID,
            role=role,
            email=f"{role}@test.sotong",
            name=f"테스트 {role}",
            password_hash=_cached_password_hash(),
        )
        db.add(user)
        made[role] = user
    db.commit()
    for user in made.values():
        db.refresh(user)
    return made


@pytest.fixture()
def tokens(users):
    """역할 → Authorization 헤더."""
    return {
        role: {"Authorization": f"Bearer {create_access_token(str(u.id), extra={'role': u.role})}"}
        for role, u in users.items()
    }


@pytest.fixture()
def assigned_teacher(db, users, student):
    """담당 교사 배정 — 접수한 민원이 이 교사에게 라우팅되도록."""
    from app.models.analysis import TeacherAssignment

    db.add(
        TeacherAssignment(
            teacher_id=users["teacher"].id, student_id=STUDENT_ID, grade=3, class_name="2"
        )
    )
    db.commit()
    return users["teacher"]
