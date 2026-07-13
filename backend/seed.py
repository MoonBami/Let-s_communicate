"""데모 시드 데이터 — 로컬에서 로그인·라우팅을 바로 테스트하기 위한 최소 계정.

실행:
    (.venv 활성화 후, backend 디렉터리에서)
    python seed.py

멱등(idempotent): 이미 있으면 건너뛴다. 비밀번호는 모두 `demo1234`.
"""

import uuid

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.analysis import TeacherAssignment
from app.models.user import School, Student, User

# 프론트(ParentComplaintPage)와 맞추기 위한 고정 UUID
SCHOOL_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
STUDENT_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")

DEMO_PASSWORD = "demo1234"

ACCOUNTS = [
    {"email": "admin@demo.sotong", "name": "데모 관리자", "role": "admin"},
    {"email": "teacher@demo.sotong", "name": "데모 교사", "role": "teacher"},
    {"email": "parent@demo.sotong", "name": "데모 학부모", "role": "parent"},
]


def main() -> None:
    db = SessionLocal()
    created: list[str] = []
    try:
        # 학교
        school = db.get(School, SCHOOL_ID)
        if school is None:
            school = School(id=SCHOOL_ID, name="소통 데모 초등학교", edu_office="데모교육청")
            db.add(school)
            created.append("school")

        # 계정
        users: dict[str, User] = {}
        for acc in ACCOUNTS:
            existing = db.execute(
                select(User).where(User.email == acc["email"])
            ).scalar_one_or_none()
            if existing is None:
                existing = User(
                    school_id=SCHOOL_ID,
                    role=acc["role"],
                    email=acc["email"],
                    name=acc["name"],
                    password_hash=hash_password(DEMO_PASSWORD),
                )
                db.add(existing)
                created.append(acc["email"])
            users[acc["role"]] = existing

        # 학생 + 교사 배정 (자동 라우팅 테스트용)
        student = db.get(Student, STUDENT_ID)
        if student is None:
            student = Student(id=STUDENT_ID, school_id=SCHOOL_ID, name="김학생", grade=3, class_name="2")
            db.add(student)
            created.append("student")

        db.flush()  # teacher.id 확보

        teacher = users["teacher"]
        exists_assign = db.execute(
            select(TeacherAssignment).where(
                TeacherAssignment.teacher_id == teacher.id,
                TeacherAssignment.student_id == STUDENT_ID,
            )
        ).scalar_one_or_none()
        if exists_assign is None:
            db.add(TeacherAssignment(teacher_id=teacher.id, student_id=STUDENT_ID, grade=3, class_name="2"))
            created.append("teacher_assignment")

        db.commit()
    finally:
        db.close()

    print("생성됨:", created or "(이미 모두 존재)")
    print("\n=== 로그인 계정 (비밀번호: %s) ===" % DEMO_PASSWORD)
    for acc in ACCOUNTS:
        print(f"  {acc['role']:8s} {acc['email']}")
    print(f"\nSCHOOL_ID = {SCHOOL_ID}")
    print(f"STUDENT_ID = {STUDENT_ID}")


if __name__ == "__main__":
    main()
