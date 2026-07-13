"""PostgreSQL 네이티브 ENUM 타입 바인딩.

db/schema.sql 이 `CREATE TYPE ... AS ENUM (...)` 로 만든 enum 과 ORM 컬럼을 맞춘다.
- 값 목록은 schema.sql / packages/shared/enums.ts 와 1:1로 유지할 것.
- create_type=False: 타입 DDL 은 schema.sql 이 담당하므로 ORM 은 생성하지 않는다.
- 각 컬럼에 새 인스턴스를 주기 위해 팩토리 함수로 제공한다.
"""

from sqlalchemy.dialects.postgresql import ENUM

_USER_ROLE = ("teacher", "parent", "admin", "mdt")
_COMPLAINT_CHANNEL = ("web_form", "chat", "call")
_COMPLAINT_CATEGORY = ("administrative", "learning", "life", "grades", "violence_dispute", "other")
_COMPLAINT_STATUS = (
    "received", "auto_answered", "filtered_blocked", "pending_teacher",
    "in_progress", "answered", "escalated", "closed",
)
_RISK_LEVEL = ("low", "medium", "high", "critical")


def user_role() -> ENUM:
    return ENUM(*_USER_ROLE, name="user_role", create_type=False)


def complaint_channel() -> ENUM:
    return ENUM(*_COMPLAINT_CHANNEL, name="complaint_channel", create_type=False)


def complaint_category() -> ENUM:
    return ENUM(*_COMPLAINT_CATEGORY, name="complaint_category", create_type=False)


def complaint_status() -> ENUM:
    return ENUM(*_COMPLAINT_STATUS, name="complaint_status", create_type=False)


def risk_level() -> ENUM:
    return ENUM(*_RISK_LEVEL, name="risk_level", create_type=False)
