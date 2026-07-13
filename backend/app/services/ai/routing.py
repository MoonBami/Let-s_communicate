"""민원 라우팅 — 담당 교사 자동 배정.

`teacher_assignments`(교사-학생/반 담당 관계)를 참조해 배정 교사를 결정한다.
1순위: 학생 직접 배정(teacher-student). 2순위: 학년·반 담당. 못 찾으면 None
(관리자가 수동 배정하도록 남겨둔다).
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.analysis import TeacherAssignment
from app.models.user import Student


def route_teacher(db: Session, student_id: uuid.UUID | None) -> uuid.UUID | None:
    if student_id is None:
        return None

    # 1) 학생에 직접 배정된 교사
    direct = db.execute(
        select(TeacherAssignment.teacher_id)
        .where(TeacherAssignment.student_id == student_id)
        .limit(1)
    ).scalar_one_or_none()
    if direct is not None:
        return direct

    # 2) 학생의 학년·반을 담당하는 교사
    student = db.get(Student, student_id)
    if student is not None and student.grade is not None:
        by_class = db.execute(
            select(TeacherAssignment.teacher_id)
            .where(
                TeacherAssignment.grade == student.grade,
                TeacherAssignment.class_name == student.class_name,
            )
            .limit(1)
        ).scalar_one_or_none()
        if by_class is not None:
            return by_class

    return None
