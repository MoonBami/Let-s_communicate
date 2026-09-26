"""라우트 테스트 — 실제 HTTP 요청 + 실제 PostgreSQL.

기존 단위 테스트는 정책 함수(`can_view_filtered`, `resolve_parent_id`)와 라우트
**배선**만 검사한다. 그것만으로는 "요청을 보냈을 때 실제로 403 이 나는가",
"DB 에 무엇이 저장되는가"를 알 수 없다. 접수자 귀속 사칭 버그가 정확히 그
틈으로 새어나갔다 — 정책은 있었지만 라우트에 연결되지 않은 상태였다.

우선순위는 **권한과 데이터 귀속**이다. 기능이 조금 덜 동작하는 것보다,
남의 민원이 보이거나 남의 명의로 민원이 들어가는 쪽이 훨씬 위험하다.

DB 가 필요하므로 `api` 마크를 단다(conftest.py 참고).
"""

import uuid

import pytest

pytestmark = pytest.mark.api

SCHOOL = "11111111-1111-1111-1111-111111111111"
STUDENT = "22222222-2222-2222-2222-222222222222"

ORDINARY = "수행평가 채점 기준을 알고 싶습니다. 확인 부탁드립니다."
ADMIN_BODY = "다음 주 급식 식단표 서류를 신청하려면 어떻게 하나요?"
ABUSIVE = "이 씨발 죽여버린다 가만 안 둬"
BULLYING = "같은 반 친구가 아이를 때려서 팔에 멍이 들었습니다. 상담을 요청드립니다."


def submit(client, body=ORDINARY, headers=None, **extra):
    payload = {"schoolId": SCHOOL, "studentId": STUDENT, "title": "t", "body": body}
    payload.update(extra)
    return client.post("/api/complaints", json=payload, headers=headers or {})


# ---------------------------------------------------------------------------
# 1. 접수자 귀속 — 사칭이 실제 요청으로 막히는가
# ---------------------------------------------------------------------------


def test_비로그인_접수는_익명으로_저장된다(client, student, users):
    r = submit(client)
    assert r.status_code == 201
    assert r.json()["parentId"] is None


def test_로그인한_학부모_접수는_본인에게_귀속(client, student, users, tokens):
    r = submit(client, headers=tokens["parent"])
    assert r.status_code == 201
    assert r.json()["parentId"] == str(users["parent"].id)


def test_본문의_parentId_로는_남의_명의를_쓸_수_없다(client, student, users):
    """이 스위트가 존재하는 이유. 수정 전에는 이 요청이 그대로 저장됐다."""
    victim = users["parent"].id
    r = submit(client, parentId=str(victim))
    assert r.status_code == 201
    assert r.json()["parentId"] is None, "본문 값이 저장되면 남의 명의로 민원을 넣을 수 있다"


def test_사칭_민원은_피해자의_mine_에_나타나지_않는다(client, student, users, tokens):
    submit(client, parentId=str(users["parent"].id), title="사칭")
    r = client.get("/api/complaints/mine", headers=tokens["parent"])
    assert r.status_code == 200
    assert r.json()["total"] == 0


def test_교직원_토큰으로_접수해도_학부모로_귀속되지_않는다(client, student, users, tokens):
    r = submit(client, headers=tokens["teacher"])
    assert r.json()["parentId"] is None


# ---------------------------------------------------------------------------
# 2. /mine — 역할 제한과 본인 격리
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("role,expected", [
    ("parent", 200), ("teacher", 403), ("admin", 403), ("mdt", 403),
])
def test_mine_은_학부모만(client, users, tokens, role, expected):
    assert client.get("/api/complaints/mine", headers=tokens[role]).status_code == expected


def test_mine_은_인증을_요구한다(client, users):
    assert client.get("/api/complaints/mine").status_code == 401


def test_mine_은_본인_민원만_돌려준다(client, student, users, tokens, db):
    """다른 학부모의 민원이 섞이면 안 된다."""
    from app.models.user import User

    other = User(school_id=uuid.UUID(SCHOOL), role="parent", email="other@test.sotong",
                 name="다른 학부모", password_hash="x")
    db.add(other)
    db.commit()
    db.refresh(other)

    from app.core.security import create_access_token
    other_headers = {"Authorization": f"Bearer {create_access_token(str(other.id))}"}

    submit(client, headers=tokens["parent"], title="내 민원")
    submit(client, headers=other_headers, title="남의 민원")

    mine = client.get("/api/complaints/mine", headers=tokens["parent"]).json()
    assert mine["total"] == 1
    assert mine["items"][0]["title"] == "내 민원"


def test_mine_에는_차단된_민원이_나오지_않는다(client, student, users, tokens):
    submit(client, body=ABUSIVE, headers=tokens["parent"], title="차단될 민원")
    assert client.get("/api/complaints/mine", headers=tokens["parent"]).json()["total"] == 0


# ---------------------------------------------------------------------------
# 3. 민원 목록 — 역할별 가시 범위
# ---------------------------------------------------------------------------


def test_학부모는_교사_민원함에_접근할_수_없다(client, users, tokens):
    assert client.get("/api/complaints", headers=tokens["parent"]).status_code == 403


def test_미인증은_목록을_볼_수_없다(client, users):
    assert client.get("/api/complaints").status_code == 401


def test_관리자는_차단된_민원까지_본다(client, student, users, tokens, assigned_teacher):
    submit(client, body=ORDINARY)
    submit(client, body=ABUSIVE)

    admin = client.get("/api/complaints", headers=tokens["admin"]).json()
    assert admin["total"] == 2
    assert any(i["filtered"] for i in admin["items"]), "증거를 찾을 화면이 여기뿐이다"


def test_교사는_차단된_민원을_보지_못한다(client, student, users, tokens, assigned_teacher):
    submit(client, body=ORDINARY)
    submit(client, body=ABUSIVE)

    teacher = client.get("/api/complaints", headers=tokens["teacher"]).json()
    assert teacher["total"] == 1
    assert not any(i["filtered"] for i in teacher["items"])


def test_교사는_본인_배정_민원만_본다(client, student, users, tokens, assigned_teacher, db):
    """다른 교사에게 배정된 민원은 보이지 않아야 한다."""
    from app.models.complaint import Complaint
    from app.models.user import User

    other = User(school_id=uuid.UUID(SCHOOL), role="teacher", email="t2@test.sotong",
                 name="다른 교사", password_hash="x")
    db.add(other)
    db.commit()
    db.refresh(other)
    db.add(Complaint(school_id=uuid.UUID(SCHOOL), body="남의 반 민원",
                     status="pending_teacher", assigned_teacher_id=other.id))
    db.commit()

    submit(client, body=ORDINARY)  # 이쪽은 assigned_teacher 에게 배정됨

    got = client.get("/api/complaints", headers=tokens["teacher"]).json()
    assert got["total"] == 1
    assert got["items"][0]["body"] != "남의 반 민원"


# ---------------------------------------------------------------------------
# 4. 민원 상세 — 건별 열람 통제
# ---------------------------------------------------------------------------


def test_교사는_차단된_민원_상세를_볼_수_없다(client, student, users, tokens, assigned_teacher):
    cid = submit(client, body=ABUSIVE).json()["id"]
    assert client.get(f"/api/complaints/{cid}", headers=tokens["teacher"]).status_code == 403


def test_관리자는_차단된_민원_상세를_볼_수_있다(client, student, users, tokens):
    cid = submit(client, body=ABUSIVE).json()["id"]
    assert client.get(f"/api/complaints/{cid}", headers=tokens["admin"]).status_code == 200


def test_교사는_남의_배정_민원_상세를_볼_수_없다(client, student, users, tokens, db):
    from app.models.complaint import Complaint

    row = Complaint(school_id=uuid.UUID(SCHOOL), body="남의 반 민원",
                    status="pending_teacher", assigned_teacher_id=users["admin"].id)
    db.add(row)
    db.commit()
    db.refresh(row)
    assert client.get(f"/api/complaints/{row.id}", headers=tokens["teacher"]).status_code == 403


def test_없는_민원은_404(client, users, tokens):
    r = client.get(f"/api/complaints/{uuid.uuid4()}", headers=tokens["admin"])
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# 5. 접수 파이프라인 결과가 DB 에 남는가
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("title", ["개새끼야", "너 죽여버릴거야", "씨발 가만 안 둬"])
def test_제목에_쓴_욕설_위협도_차단된다(client, student, users, db, title):
    """이슈 #18 회귀 — 본문만 검사하던 시절 교사 민원함에 그대로 떴다."""
    r = client.post(
        "/api/complaints",
        json={"schoolId": SCHOOL, "studentId": STUDENT, "title": title,
              "body": "우리 애 일로 확인 부탁드립니다."},
    )
    assert r.json()["status"] == "filtered_blocked", f"제목 '{title}' 가 통과했다"


def test_제목의_욕설도_증거로_보관된다(client, student, users, db):
    """차단은 됐는데 근거가 없으면 대응할 수 없다."""
    client.post(
        "/api/complaints",
        json={"schoolId": SCHOOL, "studentId": STUDENT, "title": "개새끼야",
              "body": "우리 애 일로 확인 부탁드립니다."},
    )

    from app.models.analysis import ContentFilterLog

    log = db.query(ContentFilterLog).one()
    assert "개새끼야" in log.raw_evidence


def test_제목의_위협은_위험도에도_반영된다(client, student, users, db):
    """F2 도 제목을 봐야 교사 화면의 우선순위 표시가 맞는다."""
    r = client.post(
        "/api/complaints",
        json={"schoolId": SCHOOL, "studentId": STUDENT, "title": "너 죽여버릴거야",
              "body": "우리 애 일로 확인 부탁드립니다."},
    )
    assert r.json()["risk"] in ("high", "critical")


def test_제목이_신고여도_오차단되지_않는다(client, student, users, assigned_teacher):
    """제목은 짧아 맥락이 없다 — 본문과 함께 봐야 신고가 살아남는다."""
    r = client.post(
        "/api/complaints",
        json={"schoolId": SCHOOL, "studentId": STUDENT, "title": "때려서 다쳤습니다",
              "body": "같은 반 친구가 아이를 때려서 팔에 멍이 들었습니다. 상담을 요청드립니다."},
    )
    assert r.json()["status"] == "pending_teacher"


def test_욕설_위협은_차단되고_증거가_보관된다(client, student, users, db):
    r = submit(client, body=ABUSIVE)
    assert r.json()["status"] == "filtered_blocked"

    from app.models.analysis import ContentFilterLog

    log = db.query(ContentFilterLog).one()
    assert log.is_blocked
    # 증거는 제목+본문 전체다. 본문은 한 글자도 바뀌지 않은 채 들어 있어야 하고,
    # 제목도 함께 남아야 한다(제목에 쓴 욕설이 기록에서 사라지지 않도록).
    assert ABUSIVE in log.raw_evidence, "본문이 원문 그대로 보관되어야 증거로 쓸 수 있다"
    assert log.raw_evidence.endswith(ABUSIVE), "본문이 변형·절단되면 안 된다"
    assert "t" in log.raw_evidence, "제목도 증거에 포함되어야 한다"
    assert log.matched_terms


def test_학폭_신고는_교사에게_배정된다(client, student, users, assigned_teacher):
    """F3 오차단 수정의 회귀 방지 — 이 문장은 한때 차단되어 사라졌다."""
    r = submit(client, body=BULLYING).json()
    assert r["status"] == "pending_teacher"
    assert r["category"] == "violence_dispute"
    assert r["assignedTeacherId"] == str(assigned_teacher.id)


def test_게이트가_보류한_행정민원도_교사에게_간다(client, student, users, assigned_teacher):
    """규칙 기반 분류기는 신뢰도 0.4 라 자동 응대 임계값(0.7)을 넘지 못한다."""
    r = submit(client, body=ADMIN_BODY).json()
    assert r["category"] == "administrative"
    assert r["status"] == "pending_teacher"


def test_분류와_위험분석_이력이_남는다(client, student, users, db):
    submit(client, body=ORDINARY)

    from app.models.analysis import Classification, RiskAnalysis

    assert db.query(Classification).count() == 1
    assert db.query(RiskAnalysis).count() == 1


# ---------------------------------------------------------------------------
# 6. F8 이관 · F9 대시보드 · F5 사례 권한
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("role,expected", [
    ("admin", 200), ("mdt", 200), ("teacher", 403), ("parent", 403),
])
def test_대시보드는_관리자와_MDT_만(client, users, tokens, role, expected):
    assert client.get("/api/dashboard/stats", headers=tokens[role]).status_code == expected


@pytest.mark.parametrize("role,expected", [
    ("admin", 200), ("mdt", 200), ("teacher", 403), ("parent", 403),
])
def test_이관_목록은_관리자와_MDT_만(client, users, tokens, role, expected):
    assert client.get("/api/escalations", headers=tokens[role]).status_code == expected


def test_이관_요청부터_해결까지(client, student, users, tokens, assigned_teacher):
    cid = submit(client, body=ORDINARY).json()["id"]

    created = client.post("/api/escalations", headers=tokens["teacher"],
                          json={"complaintId": cid, "reason": "단독 대응 곤란"})
    assert created.status_code == 201
    eid = created.json()["id"]

    detail = client.get(f"/api/complaints/{cid}", headers=tokens["admin"]).json()
    assert detail["status"] == "escalated"

    dup = client.post("/api/escalations", headers=tokens["teacher"],
                      json={"complaintId": cid, "reason": "중복"})
    assert dup.status_code == 409

    resolved = client.patch(f"/api/escalations/{eid}", headers=tokens["mdt"],
                            json={"status": "resolved", "resolution": "종결"})
    assert resolved.status_code == 200

    after = client.get(f"/api/complaints/{cid}", headers=tokens["admin"]).json()
    assert after["status"] == "closed"
    assert after["closedAt"] is not None


def test_이관_반송하면_교사에게_되돌아온다(client, student, users, tokens, assigned_teacher):
    cid = submit(client, body=ORDINARY).json()["id"]
    eid = client.post("/api/escalations", headers=tokens["teacher"],
                      json={"complaintId": cid, "reason": "판단 곤란"}).json()["id"]

    client.patch(f"/api/escalations/{eid}", headers=tokens["mdt"],
                 json={"status": "rejected", "resolution": "교사 대응 범위"})

    after = client.get(f"/api/complaints/{cid}", headers=tokens["admin"]).json()
    assert after["status"] == "pending_teacher", "반송된 민원은 갈 곳이 있어야 한다"


@pytest.mark.parametrize("role,expected", [
    ("admin", 201), ("mdt", 201), ("teacher", 403), ("parent", 403),
])
def test_사례_등록은_관리자와_MDT_만(client, users, tokens, role, expected):
    r = client.post("/api/cases", headers=tokens[role],
                    json={"category": "grades", "summary": "채점 기준 문의", "resolution": "기준표 안내"})
    assert r.status_code == expected


# ---------------------------------------------------------------------------
# 7. 유량 제한 — 인증 없는 접수 경로의 유일한 방어선
#
# 카운터 격리는 conftest 의 _isolate_rate_limit(autouse)가 담당한다.
# 여기서는 한도를 낮춰 실제 429 응답을 확인한다.
# ---------------------------------------------------------------------------


@pytest.fixture()
def low_limit(monkeypatch):
    """분당 한도를 3으로 낮춘다(기본 5는 테스트에서 다루기 번거롭다)."""
    from app.core import rate_limit

    monkeypatch.setattr(rate_limit.settings, "rate_limit_intake_per_minute", 3)


def test_짧은_시간에_과다_접수하면_429(client, student, users, low_limit):
    for i in range(3):
        assert submit(client).status_code == 201, f"{i + 1}번째가 막혔다"

    blocked = submit(client)
    assert blocked.status_code == 429
    assert blocked.headers.get("Retry-After"), "언제 다시 시도할지 알려줘야 한다"


def test_한도를_넘으면_민원이_저장되지_않는다(client, student, users, db, low_limit):
    from app.models.complaint import Complaint

    submit(client)
    submit(client)
    submit(client)
    submit(client)  # 거부

    assert db.query(Complaint).count() == 3, "거부된 요청이 DB 를 채우면 방어가 무의미하다"


def test_조회는_유량_제한에_걸리지_않는다(client, users, tokens, low_limit):
    """제한은 접수(POST)에만 걸린다. 목록 조회까지 막으면 교사 업무가 멈춘다."""
    for _ in range(6):
        assert client.get("/api/complaints", headers=tokens["teacher"]).status_code == 200


def test_로그인한_학부모는_IP_가_아니라_본인_기준으로_센다(client, student, users, tokens, low_limit):
    """같은 IP(테스트 클라이언트) 뒤에서도 익명 접수와 카운터가 분리되어야 한다.

    같은 학교 와이파이·NAT 뒤의 학부모들이 서로를 막지 않게 하는 성질이다.
    """
    for _ in range(3):
        submit(client)                      # 익명(IP 키) 한도 소진
    assert submit(client).status_code == 429

    # 로그인한 학부모는 사용자 키를 쓰므로 아직 여유가 있어야 한다.
    assert submit(client, headers=tokens["parent"]).status_code == 201


# ---------------------------------------------------------------------------
# 8. 인증
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", [
    "Bearer not-a-real-token",
    "Bearer ",
    "Basic dXNlcjpwYXNz",   # 다른 인증 방식
    "not-even-a-scheme",
])
def test_잘못된_토큰은_401(client, users, value):
    # 헤더 값은 ASCII 여야 하므로(httpx 가 거부) 한글을 넣지 않는다.
    assert client.get("/api/complaints", headers={"Authorization": value}).status_code == 401


def test_sub_가_UUID_가_아닌_토큰은_500_이_아니라_401(client, users):
    """위조·구버전 토큰에서 실제로 500 이 났던 자리."""
    from app.core.security import create_access_token

    bad = create_access_token("not-a-uuid")
    r = client.get("/api/complaints", headers={"Authorization": f"Bearer {bad}"})
    assert r.status_code == 401


def test_로그인하면_토큰이_나오고_me_가_동작한다(client, users):
    login = client.post("/api/auth/login",
                        json={"email": "teacher@test.sotong", "password": "test1234"})
    assert login.status_code == 200
    token = login.json()["accessToken"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["role"] == "teacher"


def test_틀린_비밀번호는_401(client, users):
    r = client.post("/api/auth/login",
                    json={"email": "teacher@test.sotong", "password": "wrong"})
    assert r.status_code == 401
