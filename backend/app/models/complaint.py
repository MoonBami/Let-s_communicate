import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models._enums import (
    complaint_category,
    complaint_channel,
    complaint_status,
    risk_level,
)


class Complaint(Base):
    __tablename__ = "complaints"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    student_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    assigned_teacher_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    channel: Mapped[str] = mapped_column(complaint_channel(), nullable=False, default="web_form")
    title: Mapped[str | None] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text, nullable=False)  # 원문 (필터 전 원본)
    category: Mapped[str | None] = mapped_column(complaint_category())  # F1 분류 결과
    status: Mapped[str] = mapped_column(complaint_status(), nullable=False, default="received")
    risk: Mapped[str] = mapped_column(risk_level(), default="low")  # F2 위험도
    is_auto_handled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    filtered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # F3
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # 비회원 조회 — 접수번호 + 숫자 4자리 비밀번호 (services/receipt.py).
    # 비밀번호는 해시로만 저장한다. 실패 횟수·잠금은 DB 에 둔다 — 서버리스(Vercel)에선
    # 인스턴스마다 메모리가 따로라 메모리 카운터로는 잠금이 유지되지 않는다.
    receipt_code: Mapped[str | None] = mapped_column(String(16), unique=True)
    lookup_pin_hash: Mapped[str | None] = mapped_column(String(255))
    lookup_fail_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lookup_locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ComplaintMessage(Base):
    """교사·관리자·MDT 가 학부모에게 보낸 답변. 학부모 회신은 받지 않는다(설계 결정)."""

    __tablename__ = "complaint_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    complaint_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False
    )
    sender_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    is_ai: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AnswerDraft(Base):
    __tablename__ = "answer_drafts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    complaint_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False
    )
    draft_body: Mapped[str] = mapped_column(Text, nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(100))
    is_adopted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    edited_body: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
