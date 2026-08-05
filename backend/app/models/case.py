"""F5: 유사 사례 지식베이스 + 임베딩.

db/schema.sql 의 complaint_cases / case_embeddings 에 대응.
`EMBEDDING_DIM` 은 DDL 의 VECTOR(1536) 과 반드시 일치해야 한다.
"""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models._enums import complaint_category

EMBEDDING_DIM = 1536


class ComplaintCase(Base):
    """과거 민원-대응 사례 (RAG 지식베이스 문서)."""

    __tablename__ = "complaint_cases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_complaint_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("complaints.id", ondelete="SET NULL")
    )
    category: Mapped[str | None] = mapped_column(complaint_category())
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    resolution: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CaseEmbedding(Base):
    """사례 임베딩. model_name 이 다른 벡터는 서로 비교하면 안 된다(검색 시 필터)."""

    __tablename__ = "case_embeddings"

    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("complaint_cases.id", ondelete="CASCADE"),
        primary_key=True,
    )
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
