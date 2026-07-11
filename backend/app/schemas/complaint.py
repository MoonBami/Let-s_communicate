import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ComplaintCreate(BaseModel):
    school_id: uuid.UUID
    student_id: uuid.UUID | None = None
    channel: str = "web_form"
    title: str | None = None
    body: str = Field(min_length=1)


class ComplaintOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    school_id: uuid.UUID
    assigned_teacher_id: uuid.UUID | None
    channel: str
    title: str | None
    body: str
    category: str | None
    status: str
    risk: str
    is_auto_handled: bool
    filtered: bool
    created_at: datetime
    updated_at: datetime


class Paginated(BaseModel):
    items: list[ComplaintOut]
    total: int
    page: int
    page_size: int


class DraftOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    complaint_id: uuid.UUID
    draft_body: str
    model_name: str | None
    is_adopted: bool
    edited_body: str | None
    created_at: datetime
