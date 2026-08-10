"""AI 처리 결과 · 라우팅 관계 모델.

db/schema.sql 의 classifications / risk_analyses / content_filter_logs /
teacher_assignments / audit_logs 에 대응. 접수 파이프라인이 남기는 이력·증거를 담는다.
"""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Numeric, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models._enums import complaint_category, risk_level


class Classification(Base):
    """F1: 분류 결과 이력."""

    __tablename__ = "classifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    complaint_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False
    )
    predicted: Mapped[str] = mapped_column(complaint_category(), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Numeric(5, 4))
    model_name: Mapped[str | None] = mapped_column(String(100))
    model_version: Mapped[str | None] = mapped_column(String(50))
    is_auto_routed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RiskAnalysis(Base):
    """F2: 감정·위험 분석 결과."""

    __tablename__ = "risk_analyses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    complaint_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False
    )
    sentiment_score: Mapped[float | None] = mapped_column(Numeric(5, 4))
    aggression_score: Mapped[float | None] = mapped_column(Numeric(5, 4))
    risk: Mapped[str] = mapped_column(risk_level(), nullable=False)
    reasons: Mapped[dict | list | None] = mapped_column(JSONB)
    model_name: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ContentFilterLog(Base):
    """F3: 욕설·위협 필터 로그 및 증거(교사 미노출 원문 보관)."""

    __tablename__ = "content_filter_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    complaint_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("complaints.id", ondelete="CASCADE")
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    is_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    matched_terms: Mapped[dict | list | None] = mapped_column(JSONB)
    severity: Mapped[str] = mapped_column(risk_level(), nullable=False, default="medium")
    raw_evidence: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TeacherAssignment(Base):
    """교사-학생/반 담당 관계 (민원 라우팅 대상 결정)."""

    __tablename__ = "teacher_assignments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    teacher_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE")
    )
    grade: Mapped[int | None] = mapped_column(SmallInteger)
    class_name: Mapped[str | None] = mapped_column(String(50))


class AuditLog(Base):
    """민감정보(차단 민원 증거 등) 접근 감사 로그.

    누가 언제 어떤 자원을 열람·조작했는지 기록한다.
    schema.sql 의 audit_logs 에 대응. 법적 요건(민감정보 접근 추적) 충족용.
    """

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(50))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    detail: Mapped[dict | list | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
