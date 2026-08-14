"""감사 로그(audit_logs) 기록 테스트.

차단된 민원(F3 증거)의 원문에는 욕설·위협과 학생·학부모 민감정보가 담긴다.
**누가 언제 그것을 열람했는지** 남기는 것은 기획 문서가 필수로 꼽은 요건이다.

원안(seongyun-ship-it, PR #6)은 `SessionLocal` 로 개발 DB 에 직접 쓰고 지우는
방식이었다. 그러면 CI 에서 돌 수 없고 개발 데이터에 흔적이 남는다. 지금은 라우트
테스트 기반으로 **실제 요청을 보내 기록이 남는지** 확인한다 — 모델이 저장되는지가
아니라 '열람하면 기록된다'는 성질이 중요하기 때문이다.
"""

import pytest

pytestmark = pytest.mark.api

SCHOOL = "11111111-1111-1111-1111-111111111111"
STUDENT = "22222222-2222-2222-2222-222222222222"
ABUSIVE = "이 씨발 죽여버린다 가만 안 둬"
ORDINARY = "수행평가 채점 기준을 알고 싶습니다. 확인 부탁드립니다."


def submit(client, body, headers=None):
    return client.post(
        "/api/complaints",
        json={"schoolId": SCHOOL, "studentId": STUDENT, "title": "t", "body": body},
        headers=headers or {},
    )


def audit_rows(db, action=None):
    from app.models.analysis import AuditLog

    q = db.query(AuditLog)
    if action:
        q = q.filter(AuditLog.action == action)
    return q.all()


# --- 차단 민원 상세 열람 -----------------------------------------------------


def test_관리자가_차단민원을_열람하면_기록된다(client, student, users, tokens, db):
    from app.services.audit import VIEW_BLOCKED_COMPLAINT

    cid = submit(client, ABUSIVE).json()["id"]
    assert client.get(f"/api/complaints/{cid}", headers=tokens["admin"]).status_code == 200

    rows = audit_rows(db, VIEW_BLOCKED_COMPLAINT)
    assert len(rows) == 1
    row = rows[0]
    assert row.user_id == users["admin"].id
    assert row.entity_type == "complaint"
    assert str(row.entity_id) == cid
    assert row.created_at is not None
    assert row.detail["role"] == "admin"


def test_MDT_열람도_기록된다(client, student, users, tokens, db):
    from app.services.audit import VIEW_BLOCKED_COMPLAINT

    cid = submit(client, ABUSIVE).json()["id"]
    client.get(f"/api/complaints/{cid}", headers=tokens["mdt"])

    rows = audit_rows(db, VIEW_BLOCKED_COMPLAINT)
    assert len(rows) == 1
    assert rows[0].user_id == users["mdt"].id


def test_차단되지_않은_민원_열람은_기록하지_않는다(client, student, users, tokens, db, assigned_teacher):
    """일반 민원까지 남기면 로그가 잡음으로 가득 차 증거 추적이 묻힌다."""
    cid = submit(client, ORDINARY).json()["id"]
    client.get(f"/api/complaints/{cid}", headers=tokens["admin"])

    assert audit_rows(db) == []


def test_교사가_차단민원_열람에_실패하면_기록하지_않는다(client, student, users, tokens, db, assigned_teacher):
    """403 으로 막힌 시도는 '열람'이 아니다. 권한 검사 뒤에 기록해야 한다."""
    cid = submit(client, ABUSIVE).json()["id"]
    assert client.get(f"/api/complaints/{cid}", headers=tokens["teacher"]).status_code == 403

    assert audit_rows(db) == []


def test_열람할수록_기록이_쌓인다(client, student, users, tokens, db):
    from app.services.audit import VIEW_BLOCKED_COMPLAINT

    cid = submit(client, ABUSIVE).json()["id"]
    for _ in range(3):
        client.get(f"/api/complaints/{cid}", headers=tokens["admin"])

    assert len(audit_rows(db, VIEW_BLOCKED_COMPLAINT)) == 3, "열람 횟수가 곧 추적 대상이다"


# --- 증거를 읽는 다른 경로도 덮이는가 ---------------------------------------


def test_초안_생성도_증거_접근으로_기록된다(client, student, users, tokens, db):
    """초안 생성은 민원 원문을 읽는다. 상세만 기록하면 이 경로가 빠진다."""
    from app.services.audit import VIEW_BLOCKED_COMPLAINT

    cid = submit(client, ABUSIVE).json()["id"]
    client.post(f"/api/complaints/{cid}/draft", headers=tokens["admin"])

    assert len(audit_rows(db, VIEW_BLOCKED_COMPLAINT)) == 1


def test_유사사례_검색도_기록된다(client, student, users, tokens, db):
    from app.services.audit import VIEW_BLOCKED_COMPLAINT

    cid = submit(client, ABUSIVE).json()["id"]
    client.get(f"/api/complaints/{cid}/similar-cases", headers=tokens["admin"])

    assert len(audit_rows(db, VIEW_BLOCKED_COMPLAINT)) == 1


# --- 목록 조회 --------------------------------------------------------------


def test_목록에_차단민원이_실리면_기록된다(client, student, users, tokens, db):
    """목록 미리보기에도 원문이 실려 나가므로 증거 접근이다."""
    from app.services.audit import LIST_BLOCKED_COMPLAINTS

    submit(client, ABUSIVE)
    submit(client, ORDINARY)
    client.get("/api/complaints", headers=tokens["admin"])

    rows = audit_rows(db, LIST_BLOCKED_COMPLAINTS)
    assert len(rows) == 1
    assert rows[0].detail["blocked_count"] == 1


def test_차단민원이_없는_목록은_기록하지_않는다(client, student, users, tokens, db, assigned_teacher):
    submit(client, ORDINARY)
    client.get("/api/complaints", headers=tokens["admin"])

    assert audit_rows(db) == []


def test_교사_목록조회는_기록하지_않는다(client, student, users, tokens, db, assigned_teacher):
    """교사에게는 차단 민원이 애초에 보이지 않으므로 남길 것도 없다."""
    submit(client, ABUSIVE)
    submit(client, ORDINARY)
    client.get("/api/complaints", headers=tokens["teacher"])

    assert audit_rows(db) == []


# --- 기록 실패가 열람을 막지 않는다 -----------------------------------------


def test_기록이_실패해도_열람은_된다(client, student, users, tokens, monkeypatch):
    """감사 로그 저장 문제로 관리자가 증거에 접근하지 못하면 대응이 멈춘다.

    정책 판단이다 — '감사 기록 없으면 열람 불가'를 요구하는 규정도 있으므로
    운영 전환 시 재검토가 필요하다(services/audit.py 참고).
    """
    from app.models import analysis

    cid = submit(client, ABUSIVE).json()["id"]

    # record() 자체를 바꾸면 그 안의 예외 처리를 건너뛰어 테스트가 무의미해진다.
    # 저장 단계만 깨뜨려 record() 의 fail-open 이 실제로 동작하는지 본다.
    def _boom(*_args, **_kwargs):
        raise RuntimeError("audit table gone")

    monkeypatch.setattr(analysis, "AuditLog", _boom)
    monkeypatch.setattr("app.services.audit.AuditLog", _boom)

    assert client.get(f"/api/complaints/{cid}", headers=tokens["admin"]).status_code == 200
