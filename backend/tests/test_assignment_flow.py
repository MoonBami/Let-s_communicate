"""교사 배정 — 회원가입한 교사가 민원을 볼 수 있게 되기까지.

배경: 교사 민원함은 `assigned_teacher_id == 본인` 만 보여주고, 배정은 접수 시
`teacher_assignments` 로 정해진다. 이 테이블을 채우는 경로가 seed.py 뿐이라
**회원가입한 교사는 몇 명을 만들어도 민원이 0건**이었다(배포 환경에서 실제로 겪음).

이제 관리자가 반을 배정한다. 동시에 막아야 할 것:
- 회원가입으로 관리자를 만들 수 있던 구멍(누구나 증거 원문 열람 가능했다)
- 교사가 스스로 담당 반을 주장하는 경로(그 반 민원을 아무나 읽게 된다)
- 다른 학교 교사에게 민원이 가는 라우팅
"""

import uuid

import pytest

from tests.conftest import SCHOOL_ID, STUDENT_ID, TEST_PASSWORD

pytestmark = pytest.mark.api

SCHOOL = str(SCHOOL_ID)
STUDENT = str(STUDENT_ID)
ORDINARY = "수행평가 채점 기준을 알고 싶습니다. 확인 부탁드립니다."
ABUSIVE = "이 씨발 죽여버린다 가만 안 둬"


def submit(client, **extra):
    payload = {"schoolId": SCHOOL, "studentId": STUDENT, "title": "t", "body": ORDINARY}
    payload.update(extra)
    return client.post("/api/complaints", json=payload)


def signup_teacher(client, email="new-teacher@test.sotong"):
    r = client.post(
        "/api/auth/signup",
        json={"email": email, "password": TEST_PASSWORD, "name": "새 교사", "role": "teacher"},
    )
    assert r.status_code == 201, r.text
    token = r.json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}
    me = client.get("/api/auth/me", headers=headers).json()
    return me["id"], headers


def inbox_total(client, headers):
    return client.get("/api/complaints", headers=headers).json()["total"]


def assign(client, tokens, teacher_id, grade=3, class_name="2", transfer=True):
    return client.post(
        "/api/admin/assignments",
        headers=tokens["admin"],
        json={"teacherId": teacher_id, "grade": grade, "className": class_name, "transferOpen": transfer},
    )


# ---------------------------------------------------------------------------
# 1. 회원가입 구멍
# ---------------------------------------------------------------------------


def test_회원가입으로_관리자를_만들_수_없다(client, users):
    r = client.post(
        "/api/auth/signup",
        json={"email": "evil@test.sotong", "password": TEST_PASSWORD, "name": "x", "role": "admin"},
    )
    assert r.status_code == 400, "가입 화면에서 관리자가 되면 차단 민원 증거를 전부 읽는다"


def test_갓_가입한_교사는_아무_민원도_못_본다(client, student, users, assigned_teacher):
    assert submit(client).status_code == 201
    _, headers = signup_teacher(client)
    assert inbox_total(client, headers) == 0


# ---------------------------------------------------------------------------
# 2. 관리자 배정 → 민원이 보인다 (이 스위트의 핵심)
# ---------------------------------------------------------------------------


def test_관리자는_소속_없는_새_교사를_목록에서_본다(client, users, tokens):
    new_id, _ = signup_teacher(client)
    teachers = client.get("/api/admin/teachers", headers=tokens["admin"]).json()
    new = next(t for t in teachers if t["id"] == new_id)
    assert new["schoolId"] is None and new["assignments"] == []
    assert teachers[0]["id"] == new_id, "미배정 교사가 먼저 와야 관리자가 놓치지 않는다"


def test_반을_배정하면_진행중_민원이_옮겨와_보인다(client, student, users, tokens, assigned_teacher):
    old = submit(client).json()
    assert old["assignedTeacherId"] == str(assigned_teacher.id)

    new_id, headers = signup_teacher(client)
    r = assign(client, tokens, new_id)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["movedComplaints"] == 1
    assert body["replaced"] == 1, "기존 담임 배정은 해제되어야 한다"

    assert inbox_total(client, headers) == 1
    assert inbox_total(client, tokens["teacher"]) == 0, "옮긴 민원이 이전 담임에게도 남으면 안 된다"


def test_배정_후_새_민원은_새_교사에게_간다(client, student, users, tokens, assigned_teacher):
    new_id, headers = signup_teacher(client)
    assign(client, tokens, new_id)

    r = submit(client).json()
    assert r["assignedTeacherId"] == new_id
    assert inbox_total(client, headers) == 1


def test_옮기지_않으면_기존_건은_이전_담임에게_남는다(client, student, users, tokens, assigned_teacher):
    submit(client)
    new_id, headers = signup_teacher(client)
    r = assign(client, tokens, new_id, transfer=False)
    assert r.json()["movedComplaints"] == 0

    assert inbox_total(client, tokens["teacher"]) == 1
    assert inbox_total(client, headers) == 0
    submit(client)
    assert inbox_total(client, headers) == 1, "새 민원부터는 새 담임에게"


def test_배정하면_교사가_관리자_학교_소속이_된다(client, users, tokens):
    new_id, headers = signup_teacher(client)
    assign(client, tokens, new_id)
    assert client.get("/api/auth/me", headers=headers).json()["schoolId"] == SCHOOL


def test_반_표기는_정규화된다(client, student, users, tokens):
    new_id, _ = signup_teacher(client)
    r = assign(client, tokens, new_id, class_name=" 2반 ")
    assert r.json()["assignment"]["className"] == "2"


def test_같은_배정을_두_번_해도_하나만_남는다(client, users, tokens):
    new_id, _ = signup_teacher(client)
    a = assign(client, tokens, new_id).json()["assignment"]["id"]
    b = assign(client, tokens, new_id).json()["assignment"]["id"]
    assert a == b


def test_배정을_해제하면_새_민원이_가지_않는다(client, student, users, tokens):
    new_id, headers = signup_teacher(client)
    aid = assign(client, tokens, new_id).json()["assignment"]["id"]
    assert client.delete(f"/api/admin/assignments/{aid}", headers=tokens["admin"]).status_code == 204

    r = submit(client).json()
    assert r["assignedTeacherId"] is None


def test_배정_기록이_감사_로그에_남는다(client, users, tokens, db):
    from sqlalchemy import select

    from app.models.analysis import AuditLog

    new_id, _ = signup_teacher(client)
    assign(client, tokens, new_id)
    db.expire_all()
    actions = db.execute(select(AuditLog.action)).scalars().all()
    assert "ASSIGN_TEACHER" in actions


# ---------------------------------------------------------------------------
# 3. 권한
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("role", ["teacher", "mdt", "parent"])
def test_배정은_관리자만(client, users, tokens, role):
    new_id, _ = signup_teacher(client)
    assert assign_as(client, tokens[role], new_id).status_code == 403
    assert client.get("/api/admin/teachers", headers=tokens[role]).status_code == 403


def assign_as(client, headers, teacher_id):
    return client.post(
        "/api/admin/assignments",
        headers=headers,
        json={"teacherId": teacher_id, "grade": 3, "className": "2"},
    )


def test_교사는_스스로_배정할_수_없다(client, users):
    new_id, headers = signup_teacher(client)
    assert assign_as(client, headers, new_id).status_code == 403


def test_다른_학교_교사는_배정할_수_없다(client, users, tokens, db):
    from app.models.user import School, User

    other = School(name="다른 학교")
    db.add(other)
    db.flush()
    t = User(school_id=other.id, role="teacher", email="other@test.sotong", name="타교 교사")
    db.add(t)
    db.commit()

    assert assign(client, tokens, str(t.id)).status_code == 404
    ids = [x["id"] for x in client.get("/api/admin/teachers", headers=tokens["admin"]).json()]
    assert str(t.id) not in ids


def test_교사가_아닌_계정은_배정할_수_없다(client, users, tokens):
    assert assign(client, tokens, str(users["mdt"].id)).status_code == 404


# ---------------------------------------------------------------------------
# 4. 라우팅은 학교를 넘지 않는다
# ---------------------------------------------------------------------------


def test_다른_학교의_같은_반_담임에게_가지_않는다(client, student, users, db):
    from app.models.analysis import TeacherAssignment
    from app.models.user import School, User

    other = School(name="다른 학교")
    db.add(other)
    db.flush()
    t = User(school_id=other.id, role="teacher", email="other@test.sotong", name="타교 3-2 담임")
    db.add(t)
    db.flush()
    db.add(TeacherAssignment(teacher_id=t.id, grade=3, class_name="2"))
    db.commit()

    r = submit(client).json()
    assert r["assignedTeacherId"] != str(t.id)
    assert r["assignedTeacherId"] is None


# ---------------------------------------------------------------------------
# 5. 개별 민원 담당 지정 — 자동 배정이 못 찾은 건의 구제 경로
# ---------------------------------------------------------------------------


def test_학생_없는_민원도_관리자가_교사에게_넘길_수_있다(client, school, users, tokens):
    r = client.post("/api/complaints", json={"schoolId": SCHOOL, "title": "t", "body": ORDINARY}).json()
    assert r["assignedTeacherId"] is None

    new_id, headers = signup_teacher(client)
    assign(client, tokens, new_id)  # 학교 소속으로 만든다
    res = client.patch(
        f"/api/complaints/{r['id']}/assignee", headers=tokens["admin"], json={"teacherId": new_id}
    )
    assert res.status_code == 200, res.text
    assert inbox_total(client, headers) == 1


def test_소속_없는_교사에게는_민원을_넘길_수_없다(client, school, users, tokens):
    r = client.post("/api/complaints", json={"schoolId": SCHOOL, "body": ORDINARY}).json()
    new_id, _ = signup_teacher(client)
    res = client.patch(
        f"/api/complaints/{r['id']}/assignee", headers=tokens["admin"], json={"teacherId": new_id}
    )
    assert res.status_code == 404, "반 배정으로 학교 소속이 확인된 교사에게만 넘긴다"


def test_차단된_민원은_교사에게_넘길_수_없다(client, student, users, tokens):
    r = submit(client, body=ABUSIVE).json()
    assert r["filtered"] is True
    res = client.patch(
        f"/api/complaints/{r['id']}/assignee",
        headers=tokens["admin"],
        json={"teacherId": str(users["teacher"].id)},
    )
    assert res.status_code == 409


@pytest.mark.parametrize("role", ["teacher", "mdt"])
def test_민원_담당_지정은_관리자만(client, student, users, tokens, role):
    r = submit(client).json()
    res = client.patch(
        f"/api/complaints/{r['id']}/assignee",
        headers=tokens[role],
        json={"teacherId": str(users["teacher"].id)},
    )
    assert res.status_code == 403


def test_없는_민원_담당_지정은_404(client, users, tokens):
    res = client.patch(
        f"/api/complaints/{uuid.uuid4()}/assignee",
        headers=tokens["admin"],
        json={"teacherId": str(users["teacher"].id)},
    )
    assert res.status_code == 404
