import uuid
from datetime import datetime

from pydantic import Field

from app.schemas.base import CamelModel


class EscalationCreate(CamelModel):
    """교사 → MDT/관리자 이관 요청. 사유는 대응 판단 근거라 필수."""

    complaint_id: uuid.UUID
    reason: str = Field(min_length=1)


class EscalationUpdate(CamelModel):
    """MDT/관리자의 처리 — accepted(접수) / resolved(해결) / rejected(반송)."""

    status: str
    resolution: str | None = None


class EscalationOut(CamelModel):
    id: uuid.UUID
    complaint_id: uuid.UUID
    requested_by: uuid.UUID | None
    assigned_to: uuid.UUID | None
    status: str
    reason: str | None
    resolution: str | None
    created_at: datetime
    resolved_at: datetime | None
