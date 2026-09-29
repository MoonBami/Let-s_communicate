"""민원 라우팅 — 담당 교사 자동 배정.

`teacher_assignments`(교사-학생/반 담당 관계)를 참조해 배정 교사를 결정한다.
1순위: 학생 직접 배정(teacher-student). 2순위: 학년·반 담당. 못 찾으면 None
(관리자가 수동 배정하도록 남겨둔다 — `PATCH /api/complaints/{id}/assignee`).

학생 명단에 없는 학생이라도 학부모가 학년·반을 적었으면 그 반 담당에게 보낸다
(`route_by_class`). 학교가 명단을 올리지 않아도 반 배정만으로 자동 배정이 돌게
하려는 것이다. 대가: 학부모가 반을 잘못 적으면 그 반 담임에게 간다 — 학부모 본인이
준 정보라 감수하고, 담임이 관리자에게 재배정을 요청하면 된다.

**같은 학교의 활성 교사만 고른다.** 전에는 학년·반만 비교해서, A 학교의 3학년 2반
민원이 B 학교 3학년 2반 담임에게 갈 수 있었다. 민원 내용이 다른 학교 교사에게
노출되는 것이라 학교 조건을 모든 단계에 건다. 교사의 학교는 `users.school_id` 다
(관리자가 반을 배정할 때 채워진다 — routes/admin.py).
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.analysis import TeacherAssignment
from app.models.user import Student, User


def _teachers_of_school(school_id: uuid.UUID):
    return (
        select(TeacherAssignment.teacher_id)
        .join(User, User.id == TeacherAssignment.teacher_id)
        .where(
            User.school_id == school_id,
            User.role == "teacher",
            User.is_active.is_(True),
        )
    )


def route_teacher(
    db: Session, school_id: uuid.UUID, student_id: uuid.UUID | None
) -> uuid.UUID | None:
    if student_id is None:
        return None

    student = db.get(Student, student_id)
    if student is None or student.school_id != school_id:
        return None

    # 1) 학생에 직접 배정된 교사
    direct = db.execute(
        _teachers_of_school(school_id)
        .where(TeacherAssignment.student_id == student_id)
        .limit(1)
    ).scalar_one_or_none()
    if direct is not None:
        return direct

    # 2) 학생의 학년·반을 담당하는 교사
    if student.grade is not None and student.class_name is not None:
        return route_by_class(db, school_id, student.grade, student.class_name)

    return None


def route_by_class(
    db: Session, school_id: uuid.UUID, grade: int, class_name: str
) -> uuid.UUID | None:
    """이 학교에서 학년·반을 담당하는 교사. class_name 은 정규화된 값('2')이어야 한다."""
    return db.execute(
        _teachers_of_school(school_id)
        .where(
            TeacherAssignment.grade == grade,
            TeacherAssignment.class_name == class_name,
        )
        .limit(1)
    ).scalar_one_or_none()
