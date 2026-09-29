import uuid

from pydantic import Field

from app.schemas.base import CamelModel


class AssignmentOut(CamelModel):
    id: uuid.UUID
    teacher_id: uuid.UUID
    student_id: uuid.UUID | None
    grade: int | None
    class_name: str | None


class TeacherOut(CamelModel):
    """관리자 배정 화면용 교사 요약. 소속 학교가 없으면(갓 가입) 미배정 교사다."""

    id: uuid.UUID
    name: str
    email: str | None
    school_id: uuid.UUID | None
    is_active: bool
    assignments: list[AssignmentOut] = Field(default_factory=list)
    open_complaints: int = 0


class AssignmentCreate(CamelModel):
    teacher_id: uuid.UUID
    grade: int = Field(ge=1, le=12)
    class_name: str = Field(min_length=1, max_length=50)
    # 이 반 학생의 진행 중 민원을 새 담당 교사에게 옮길지. 담임 교체라면 보통 옮긴다.
    transfer_open: bool = True


class AssignmentResult(CamelModel):
    assignment: AssignmentOut
    replaced: int  # 이 반을 맡고 있던 다른 교사의 배정을 몇 건 해제했는가
    moved_complaints: int  # 새 담당 교사에게 옮긴 민원 수
