import uuid
from datetime import datetime

from pydantic import Field

from app.schemas.base import CamelModel


class CaseCreate(CamelModel):
    """F5 지식베이스에 과거 사례를 등록."""

    source_complaint_id: uuid.UUID | None = None
    category: str | None = None
    summary: str = Field(min_length=1)
    resolution: str = Field(min_length=1)


class CaseOut(CamelModel):
    id: uuid.UUID
    source_complaint_id: uuid.UUID | None
    category: str | None
    summary: str
    resolution: str
    created_at: datetime


class SimilarCaseOut(CamelModel):
    case_id: uuid.UUID
    category: str | None
    summary: str
    resolution: str
    similarity: float  # 0~1 (코사인 유사도)
