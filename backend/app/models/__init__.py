# 대표 모델만 스캐폴딩. 전체 테이블은 db/schema.sql 참조하여 동일 패턴으로 확장.
from app.models.user import School, Student, User  # noqa: F401
from app.models.complaint import AnswerDraft, Complaint  # noqa: F401
from app.models.analysis import (  # noqa: F401
    AuditLog,
    Classification,
    ContentFilterLog,
    RiskAnalysis,
    TeacherAssignment,
)
