# ORM 모델 배럴. 아직 커버하지 않은 테이블은 db/schema.sql 참조하여 동일 패턴으로 확장.
from app.models.user import School, Student, User  # noqa: F401
from app.models.complaint import AnswerDraft, Complaint  # noqa: F401
from app.models.analysis import (  # noqa: F401
    Classification,
    ContentFilterLog,
    RiskAnalysis,
    TeacherAssignment,
)
from app.models.case import CaseEmbedding, ComplaintCase  # noqa: F401
from app.models.escalation import Escalation  # noqa: F401
from app.models.recording import Recording, Transcript  # noqa: F401
