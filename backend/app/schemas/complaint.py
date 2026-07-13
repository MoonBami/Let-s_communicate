import uuid
from datetime import datetime

from pydantic import Field, field_validator

from app.schemas.base import CamelModel


class ComplaintCreate(CamelModel):
    school_id: uuid.UUID
    student_id: uuid.UUID | None = None
    channel: str = "web_form"
    title: str | None = None
    body: str = Field(min_length=1)


class ComplaintOut(CamelModel):
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


class Paginated(CamelModel):
    items: list[ComplaintOut]
    total: int
    page: int
    page_size: int


class ClassificationOut(CamelModel):
    predicted: str
    confidence: float | None
    model_name: str | None


class RiskOut(CamelModel):
    sentiment_score: float | None
    aggression_score: float | None
    risk: str
    reasons: list[str] = Field(default_factory=list)
    model_name: str | None

    @field_validator("reasons", mode="before")
    @classmethod
    def _coerce_reasons(cls, v: object) -> list[str]:
        # JSONB 컬럼은 None·dict·list 무엇이든 올 수 있어 방어적으로 리스트화.
        if v is None:
            return []
        if isinstance(v, list):
            return [str(x) for x in v]
        return [str(v)]


class ComplaintDetail(ComplaintOut):
    """민원 상세 — 최신 분류·위험 분석을 함께 노출.

    필터 증거(matched_terms/raw_evidence)는 admin·mdt 만 접근 가능하도록
    라우트에서 통제한다(여기엔 담지 않음).
    """

    classification: ClassificationOut | None = None
    risk_analysis: RiskOut | None = None


class DraftOut(CamelModel):
    id: uuid.UUID
    complaint_id: uuid.UUID
    draft_body: str
    model_name: str | None
    is_adopted: bool
    edited_body: str | None
    created_at: datetime
