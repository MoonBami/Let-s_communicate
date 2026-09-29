"""학교 코드 조회 · 학생 찾기 · 없는 학교 404.

전에는 프론트가 데모 학교·학생 UUID 를 하드코딩해 보냈고, DB 에 그 학교가 없으면
(배포 DB 에 시드를 안 넣었을 때처럼) FK 위반이 커밋에서 터져 **500** 이 났다.
"""

import uuid

import pytest

from tests.conftest import SCHOOL_ID, STUDENT_ID

pytestmark = pytest.mark.api

SCHOOL = str(SCHOOL_ID)
ORDINARY = "수행평가 채점 기준을 알고 싶습니다. 확인 부탁드립니다."


@pytest.fixture()
def coded_school(db, school):
    school.code = "DEMO001"
    db.commit()
    return school


def count_complaints(db):
    from sqlalchemy import func, select

    from app.models.complaint import Complaint

    db.expire_all()
    return db.execute(select(func.count()).select_from(Complaint)).scalar_one()


# --- 학교 코드 -------------------------------------------------------------


def test_학교_코드로_학교를_찾는다(client, coded_school):
    r = client.get("/api/schools/by-code/DEMO001")
    assert r.status_code == 200
    assert r.json() == {"id": SCHOOL, "code": "DEMO001", "name": "테스트 초등학교", "eduOffice": None}


def test_학교_코드는_대소문자와_공백을_가리지_않는다(client, coded_school):
    assert client.get("/api/schools/by-code/%20demo001%20").status_code == 200


@pytest.mark.parametrize("code", ["NOPE999", "a", "../../etc"])
def test_없거나_이상한_코드는_404(client, coded_school, code):
    assert client.get(f"/api/schools/by-code/{code}").status_code == 404


def test_학교_조회는_공개_정보만_준다(client, coded_school):
    assert set(client.get("/api/schools/by-code/DEMO001").json()) == {"id", "code", "name", "eduOffice"}


# --- 없는 학교 → 404 --------------------------------------------------------


def test_없는_학교로_접수하면_500_이_아니라_404(client, db, users):
    r = client.post("/api/complaints", json={"schoolId": str(uuid.uuid4()), "body": ORDINARY})
    assert r.status_code == 404
    assert count_complaints(db) == 0


def test_없는_학생_id_는_404(client, school):
    r = client.post(
        "/api/complaints", json={"schoolId": SCHOOL, "studentId": str(uuid.uuid4()), "body": ORDINARY}
    )
    assert r.status_code == 404


def test_다른_학교_학생_id_는_없는_학생과_같다(client, db, school):
    from app.models.user import School, Student

    other = School(name="다른 학교")
    db.add(other)
    db.flush()
    kid = Student(school_id=other.id, name="남의학생", grade=3, class_name="2")
    db.add(kid)
    db.commit()

    r = client.post(
        "/api/complaints", json={"schoolId": SCHOOL, "studentId": str(kid.id), "body": ORDINARY}
    )
    assert r.status_code == 404


# --- 이름·학년·반으로 학생 찾기 --------------------------------------------


def lookup(client, name="김학생", grade=3, class_name="2반"):
    return client.post(
        "/api/complaints",
        json={
            "schoolId": SCHOOL,
            "student": {"name": name, "grade": grade, "className": class_name},
            "body": ORDINARY,
        },
    )


def stored_student(db, complaint_id):
    from app.models.complaint import Complaint

    db.expire_all()
    return db.get(Complaint, complaint_id).student_id


def test_이름_학년_반으로_학생을_연결한다(client, db, student, assigned_teacher):
    r = lookup(client)
    assert r.status_code == 201
    assert stored_student(db, r.json()["id"]) == STUDENT_ID


def test_이름으로_찾은_결과는_응답에_드러나지_않는다(client, student, assigned_teacher):
    """드러나면 로그인 없이 이름을 바꿔 넣어 보며 아이의 재학 여부를 캐낼 수 있다."""
    hit = lookup(client).json()
    miss = lookup(client, name="없는아이").json()
    for field in ("studentId", "assignedTeacherId", "status"):
        assert hit[field] == miss[field], field


def test_연결된_민원은_담임에게_간다(client, student, tokens, assigned_teacher):
    lookup(client)
    assert client.get("/api/complaints", headers=tokens["teacher"]).json()["total"] == 1


def test_못_찾아도_접수는_된다(client, db, student):
    r = lookup(client, name="없는아이")
    assert r.status_code == 201
    assert stored_student(db, r.json()["id"]) is None


def test_동명이인이면_연결하지_않는다(client, db, student):
    from app.models.user import Student

    db.add(Student(school_id=SCHOOL_ID, name="김학생", grade=3, class_name="2"))
    db.commit()
    r = lookup(client)
    assert stored_student(db, r.json()["id"]) is None, "엉뚱한 아이의 담임에게 가느니 관리자가 배정한다"


def test_학생_id_와_이름을_함께_보내면_422(client, school):
    r = client.post(
        "/api/complaints",
        json={
            "schoolId": SCHOOL,
            "studentId": str(STUDENT_ID),
            "student": {"name": "김학생", "grade": 3, "className": "2"},
            "body": ORDINARY,
        },
    )
    assert r.status_code == 422


def test_학교_조회를_과다하게_하면_429_지만_접수는_막히지_않는다(client, coded_school, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "rate_limit_school_lookup_per_minute", 2)
    codes = [client.get("/api/schools/by-code/DEMO001").status_code for _ in range(3)]
    assert codes == [200, 200, 429]
    r = client.post("/api/complaints", json={"schoolId": SCHOOL, "body": ORDINARY})
    assert r.status_code == 201, "조회 카운터와 접수 카운터는 따로 센다"


# --- 명단에 없는 학생 → 학부모가 적은 반의 담임 ------------------------------


def class_teacher(db, grade=2, class_name="2", school_id=SCHOOL_ID, email="t22@test.sotong"):
    from app.models.analysis import TeacherAssignment
    from app.models.user import User

    t = User(school_id=school_id, role="teacher", email=email, name="2-2 담임")
    db.add(t)
    db.flush()
    db.add(TeacherAssignment(teacher_id=t.id, grade=grade, class_name=class_name))
    db.commit()
    return t


def assigned_of(db, complaint_id):
    from app.models.complaint import Complaint

    db.expire_all()
    return db.get(Complaint, complaint_id).assigned_teacher_id


def test_명단에_없어도_적은_반의_담임에게_간다(client, db, school):
    """학교가 학생 명단을 안 올려도, 반만 배정해 두면 자동 배정이 돌아야 한다."""
    t = class_teacher(db)
    r = lookup(client, name="명단에없는아이", grade=2, class_name="2반")
    assert r.status_code == 201
    assert assigned_of(db, r.json()["id"]) == t.id
    assert stored_student(db, r.json()["id"]) is None, "학생은 여전히 연결하지 않는다"


def test_명단_기준_배정이_적은_반보다_우선한다(client, db, student, assigned_teacher):
    """명단에서 찾은 학생이면 그 학생의 실제 담임에게 간다."""
    class_teacher(db, grade=3, class_name="9")
    r = lookup(client)  # 김학생 3-2
    assert assigned_of(db, r.json()["id"]) == assigned_teacher.id


def test_적은_반_배정도_다른_학교로_넘어가지_않는다(client, db, school):
    from app.models.user import School

    other = School(name="다른 학교")
    db.add(other)
    db.commit()
    class_teacher(db, school_id=other.id, email="other22@test.sotong")
    r = lookup(client, name="아무개", grade=2, class_name="2")
    assert assigned_of(db, r.json()["id"]) is None


def test_적은_반으로_배정돼도_응답에는_드러나지_않는다(client, db, school):
    class_teacher(db)
    r = lookup(client, name="아무개", grade=2, class_name="2").json()
    assert r["assignedTeacherId"] is None
