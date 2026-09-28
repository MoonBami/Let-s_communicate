"""관리자 — 교사 담당 반 배정.

교사에게 민원이 보이려면 접수 시 라우팅(`services/ai/routing.py`)이 그 교사를
골라야 하고, 라우팅은 `teacher_assignments` 만 본다. 전에는 이 테이블을 채우는
경로가 seed.py 뿐이라 **회원가입한 교사는 민원을 영원히 볼 수 없었다.**

배정은 곧 "이 교사가 이 반 학부모 민원을 읽는다"는 권한이다. 그래서 교사 본인이
아니라 **관리자만** 한다(가입 시 본인이 담당 반을 주장하게 하면 아무나 그 반 민원을
읽는다 — routes/auth.py). 배정·해제는 감사 로그에 남긴다.

범위는 관리자의 소속 학교다. 소속 학교가 없는 교사(갓 가입)는 배정하는 순간 그
학교 소속이 된다. 다른 학교 교사는 보이지도, 배정되지도 않는다.

한 반의 담당은 한 명으로 본다(담임). 새 교사를 배정하면 그 반을 맡던 다른 교사의
배정은 해제되고, `transferOpen` 이면 진행 중 민원도 새 교사에게 옮긴다. 옮기지
않으면 이전 담당이 계속 처리하고 새 민원부터 새 교사에게 간다.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session

from app.api.deps import client_ip, require_roles
from app.db.session import get_db
from app.models.analysis import TeacherAssignment
from app.models.complaint import Complaint
from app.models.user import Student, User
from app.schemas.assignment import (
    AssignmentCreate,
    AssignmentOut,
    AssignmentResult,
    TeacherOut,
)
from app.services import audit
from app.services.directory import normalize_class_name

router = APIRouter(prefix="/api/admin", tags=["admin"])

admin_only = require_roles("admin")

# 담당 교사가 처리해야 할 상태. 이관·답변·종결 건은 옮기지 않는다.
_OPEN_STATUSES = ("received", "pending_teacher", "in_progress")


def _admin_school(current: User) -> uuid.UUID:
    if current.school_id is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "관리자 계정에 소속 학교가 없어 교사를 배정할 수 없습니다.",
        )
    return current.school_id


def _load_teacher(db: Session, teacher_id: uuid.UUID, school_id: uuid.UUID) -> User:
    """이 학교 교사이거나 아직 소속이 없는 교사. 다른 학교 교사는 없는 것으로 취급."""
    teacher = db.get(User, teacher_id)
    if (
        teacher is None
        or teacher.role != "teacher"
        or not teacher.is_active
        or teacher.school_id not in (None, school_id)
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "배정할 수 있는 교사를 찾을 수 없습니다.")
    return teacher


@router.get("/teachers", response_model=list[TeacherOut])
def list_teachers(db: Session = Depends(get_db), current: User = Depends(admin_only)):
    """이 학교 교사 + 소속 없는(갓 가입한) 교사. 미배정 교사가 먼저 온다."""
    school_id = _admin_school(current)
    teachers = db.execute(
        select(User)
        .where(
            User.role == "teacher",
            or_(User.school_id == school_id, User.school_id.is_(None)),
        )
        .order_by(User.created_at.desc())
    ).scalars().all()
    if not teachers:
        return []

    ids = [t.id for t in teachers]
    rows = db.execute(
        select(TeacherAssignment).where(TeacherAssignment.teacher_id.in_(ids))
    ).scalars().all()
    by_teacher: dict[uuid.UUID, list[AssignmentOut]] = {}
    for row in rows:
        by_teacher.setdefault(row.teacher_id, []).append(AssignmentOut.model_validate(row))

    counts = dict(
        db.execute(
            select(Complaint.assigned_teacher_id, func.count())
            .where(
                Complaint.assigned_teacher_id.in_(ids),
                Complaint.status.in_(_OPEN_STATUSES),
                Complaint.filtered.is_(False),
            )
            .group_by(Complaint.assigned_teacher_id)
        ).all()
    )

    out = [
        TeacherOut(
            id=t.id,
            name=t.name,
            email=t.email,
            school_id=t.school_id,
            is_active=t.is_active,
            assignments=by_teacher.get(t.id, []),
            open_complaints=counts.get(t.id, 0),
        )
        for t in teachers
    ]
    out.sort(key=lambda t: len(t.assignments) > 0)  # 미배정 먼저(안정 정렬)
    return out


@router.post("/assignments", response_model=AssignmentResult, status_code=status.HTTP_201_CREATED)
def assign_class(
    payload: AssignmentCreate,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(admin_only),
):
    """교사에게 학년·반을 맡긴다. 그 반의 기존 담당은 해제된다."""
    school_id = _admin_school(current)
    teacher = _load_teacher(db, payload.teacher_id, school_id)
    grade = payload.grade
    class_name = normalize_class_name(payload.class_name)
    if not class_name:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "반을 입력해 주세요.")

    if teacher.school_id is None:
        teacher.school_id = school_id  # 소속 없는 교사를 이 학교로 들인다

    class_students = select(Student.id).where(
        Student.school_id == school_id,
        Student.grade == grade,
        Student.class_name == class_name,
    )
    school_teachers = select(User.id).where(User.school_id == school_id, User.role == "teacher")

    # 이 반을 맡던 다른 교사의 배정 해제 — 반 단위 배정과, 이 반 학생 직접 배정 모두.
    # 학생 직접 배정이 라우팅 1순위라서 남겨두면 새 담임에게 민원이 가지 않는다.
    replaced = db.execute(
        delete(TeacherAssignment)
        .where(
            TeacherAssignment.teacher_id != teacher.id,
            TeacherAssignment.teacher_id.in_(school_teachers),
            or_(
                (TeacherAssignment.grade == grade) & (TeacherAssignment.class_name == class_name),
                TeacherAssignment.student_id.in_(class_students),
            ),
        )
        .execution_options(synchronize_session=False)
    ).rowcount

    assignment = db.execute(
        select(TeacherAssignment).where(
            TeacherAssignment.teacher_id == teacher.id,
            TeacherAssignment.student_id.is_(None),
            TeacherAssignment.grade == grade,
            TeacherAssignment.class_name == class_name,
        )
    ).scalar_one_or_none()
    if assignment is None:
        assignment = TeacherAssignment(teacher_id=teacher.id, grade=grade, class_name=class_name)
        db.add(assignment)

    moved = 0
    if payload.transfer_open:
        moved = db.execute(
            update(Complaint)
            .where(
                Complaint.school_id == school_id,
                Complaint.student_id.in_(class_students),
                Complaint.filtered.is_(False),
                Complaint.status.in_(_OPEN_STATUSES),
                or_(
                    Complaint.assigned_teacher_id.is_(None),
                    Complaint.assigned_teacher_id != teacher.id,
                ),
            )
            .values(assigned_teacher_id=teacher.id, status="pending_teacher")
            .execution_options(synchronize_session=False)
        ).rowcount

    db.commit()
    db.refresh(assignment)

    audit.record(
        db,
        user_id=current.id,
        action=audit.ASSIGN_TEACHER,
        entity_type="teacher_assignment",
        entity_id=assignment.id,
        ip_address=client_ip(request),
        detail={
            "teacher_id": str(teacher.id),
            "grade": grade,
            "class_name": class_name,
            "replaced": replaced,
            "moved_complaints": moved,
        },
    )
    return AssignmentResult(
        assignment=AssignmentOut.model_validate(assignment),
        replaced=replaced,
        moved_complaints=moved,
    )


@router.delete("/assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_assignment(
    assignment_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(admin_only),
):
    """배정 해제. 이미 배정된 민원은 그대로 두고, 새 민원만 더 이상 가지 않는다."""
    school_id = _admin_school(current)
    assignment = db.get(TeacherAssignment, assignment_id)
    teacher = db.get(User, assignment.teacher_id) if assignment is not None else None
    if assignment is None or teacher is None or teacher.school_id != school_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "배정을 찾을 수 없습니다.")

    detail = {
        "teacher_id": str(assignment.teacher_id),
        "grade": assignment.grade,
        "class_name": assignment.class_name,
        "student_id": str(assignment.student_id) if assignment.student_id else None,
    }
    db.delete(assignment)
    db.commit()
    audit.record(
        db,
        user_id=current.id,
        action=audit.UNASSIGN_TEACHER,
        entity_type="teacher_assignment",
        entity_id=assignment_id,
        ip_address=client_ip(request),
        detail=detail,
    )
