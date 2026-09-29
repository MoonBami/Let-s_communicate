"""데모 시드 데이터 — 로컬에서 로그인·라우팅·유사 사례를 바로 테스트하기 위한 최소 데이터.

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
from app.models.case import ComplaintCase
from app.models.user import School, Student, User
from app.services.ai import index_case

# 테스트·데모 문서와 맞추기 위한 고정 UUID (프론트는 이제 학교 코드로 찾는다)
SCHOOL_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
STUDENT_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
# 학부모가 접수 화면에 입력하는 학교 코드. 실제 교육청 코드(숫자 7자리)와 겹치지 않게 문자로.
SCHOOL_CODE = "DEMO001"

DEMO_PASSWORD = "demo1234"

ACCOUNTS = [
    {"email": "admin@demo.sotong", "name": "데모 관리자", "role": "admin"},
    {"email": "teacher@demo.sotong", "name": "데모 교사", "role": "teacher"},
    {"email": "mdt@demo.sotong", "name": "데모 민원대응팀", "role": "mdt"},
    {"email": "parent@demo.sotong", "name": "데모 학부모", "role": "parent"},
]

# F5 유사 사례 검색이 바로 결과를 내도록 하는 최소 지식베이스
DEMO_CASES = [
    {
        "category": "grades",
        "summary": "수행평가 점수 산정 기준이 불투명하다는 학부모 이의 제기",
        "resolution": "평가 기준표와 배점 근거를 문서로 안내하고, 재검토 요청 절차를 함께 고지",
    },
    {
        "category": "life",
        "summary": "교실에서 친구와 다툰 뒤 지도 방식에 대한 학부모 항의",
        "resolution": "양측 학생 면담 기록을 공유하고 담임·상담교사 합동 면담 일정을 제안",
    },
    {
        "category": "violence_dispute",
        "summary": "지속적인 괴롭힘을 주장하며 즉각 조치를 요구한 민원",
        "resolution": "학교폭력 사안으로 접수해 전담기구에 이관, 분리 조치와 상담을 병행",
    },
    {
        "category": "learning",
        "summary": "수업 진도가 빨라 아이가 따라가지 못한다는 학습 지도 문의",
        "resolution": "단원별 보충 자료 제공과 방과후 보충 학습 참여 안내",
    },
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
        if school.code is None:
            # 코드 컬럼이 생기기 전에 시드된 DB 도 채운다(db/migrations/20260929_school_code.sql 이후).
            school.code = SCHOOL_CODE
            created.append(f"school_code:{SCHOOL_CODE}")

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

        # F5 지식베이스 — summary 로 중복 판단(멱등)
        for spec in DEMO_CASES:
            existing_case = db.execute(
                select(ComplaintCase).where(ComplaintCase.summary == spec["summary"])
            ).scalar_one_or_none()
            if existing_case is not None:
                continue
            case = ComplaintCase(**spec)
            db.add(case)
            db.flush()  # case.id 확보 (임베딩 FK용)
            index_case(db, case)
            created.append(f"case:{spec['category']}")

        db.commit()
    finally:
        db.close()

    print("생성됨:", created or "(이미 모두 존재)")
    print("\n=== 로그인 계정 (비밀번호: %s) ===" % DEMO_PASSWORD)
    for acc in ACCOUNTS:
        print(f"  {acc['role']:8s} {acc['email']}")
    print(f"\nSCHOOL_ID = {SCHOOL_ID}")
    print(f"STUDENT_ID = {STUDENT_ID}")
    print(f"학교 코드 = {SCHOOL_CODE}  (학부모 접수 화면에 입력, 학생: 김학생 3학년 2반)")


if __name__ == "__main__":
    main()
