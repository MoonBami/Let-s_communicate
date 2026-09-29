import uuid
from datetime import datetime
from enum import Enum

from pydantic import Field, field_validator, model_validator

from app.schemas.base import CamelModel


class ChannelEnum(str, Enum):
    """민원 접수 경로. DB enum(complaint_channel)과 값이 일치해야 한다."""

    web_form = "web_form"
    chat = "chat"
    call = "call"


class StudentLookup(CamelModel):
    """학부모가 입력한 학생 정보 — 서버가 학교 안에서 학생을 찾는 데 쓴다.

    학부모는 학생 UUID 를 알 수 없으므로 이름·학년·반으로 받는다. 셋 다 필수다 —
    이름만으로 찾으면 동명이인에게 연결될 위험이 커진다(services/directory.py).
    """

    name: str = Field(min_length=1, max_length=100)
    grade: int = Field(ge=1, le=12)
    class_name: str = Field(min_length=1, max_length=50)


class ComplaintCreate(CamelModel):
    """민원 접수 입력.

    `parent_id` 는 **의도적으로 없다.** 접수 경로는 인증이 없으므로 본문의
    값을 신뢰하면 제3자가 임의의 학부모 명의로 민원을 넣을 수 있다.
    접수자 귀속은 서버가 토큰에서 결정한다(`deps.resolve_parent_id`).
    """

    school_id: uuid.UUID
    student_id: uuid.UUID | None = None
    student: StudentLookup | None = None
    channel: ChannelEnum = ChannelEnum.web_form
    title: str | None = None
    body: str = Field(min_length=1)
    # 비회원 조회용 숫자 4자리 비밀번호. 주면 접수번호가 발급된다(services/receipt.py).
    pin: str | None = Field(default=None, pattern=r"^\d{4}$")

    @model_validator(mode="after")
    def _one_way_to_name_student(self) -> "ComplaintCreate":
        # 둘 다 오면 어느 쪽을 믿을지가 모호하다. 조용히 한쪽을 고르면
        # 학부모가 입력한 학생과 다른 학생에게 연결될 수 있으므로 거부한다.
        if self.student_id is not None and self.student is not None:
            raise ValueError("studentId 와 student 중 하나만 보낼 수 있습니다.")
        return self


class ComplaintAssign(CamelModel):
    """관리자가 민원의 담당 교사를 지정·변경한다."""

    teacher_id: uuid.UUID


class ComplaintOut(CamelModel):
    id: uuid.UUID
    school_id: uuid.UUID
    parent_id: uuid.UUID | None
    student_id: uuid.UUID | None
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
    closed_at: datetime | None


class ComplaintCreated(ComplaintOut):
    """접수 응답. 접수번호는 **이 응답에서만** 나간다 — 다시 알려주는 경로는 없다."""

    receipt_code: str | None = None  # 'ABCD-2345' (pin 을 줬을 때만)


class MessageCreate(CamelModel):
    body: str = Field(min_length=1, max_length=5000)
    # AI 초안을 고쳐 보냈다면 그 초안 id — 채택 여부를 남겨 F4 품질 지표로 쓴다.
    draft_id: uuid.UUID | None = None


class MessageOut(CamelModel):
    id: uuid.UUID
    body: str
    sender_id: uuid.UUID | None
    sender_name: str | None = None
    sender_role: str | None = None
    created_at: datetime


class GuestLookupRequest(CamelModel):
    receipt_code: str = Field(min_length=1, max_length=20)
    pin: str = Field(min_length=1, max_length=10)


class GuestAnswer(CamelModel):
    body: str
    sender_label: str  # '담임 선생님' 등 — 교직원 계정 정보는 내보내지 않는다
    created_at: datetime


class GuestComplaintView(CamelModel):
    """비회원 조회 결과. 학부모 본인이 쓴 내용과 처리 상태, 받은 답변만 담는다.
    AI 분류·위험도·배정 교사 같은 내부 정보는 넣지 않는다."""

    receipt_code: str
    title: str | None
    body: str
    status: str
    created_at: datetime
    updated_at: datetime
    answers: list[GuestAnswer] = Field(default_factory=list)


class Paginated(CamelModel):
    items: list[ComplaintOut]
    total: int
    page: int
    page_size: int


class ClassificationOut(CamelModel):
    predicted: str
    confidence: float | None
    model_name: str | None
    is_auto_routed: bool


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
    messages: list[MessageOut] = Field(default_factory=list)


class DraftOut(CamelModel):
    id: uuid.UUID
    complaint_id: uuid.UUID
    draft_body: str
    model_name: str | None
    is_adopted: bool
    edited_body: str | None
    created_at: datetime
