"""교사 답변 → 학부모(비회원) 확인.

설계 결정(팀 합의):
- 학부모는 접수번호 + 숫자 4자리 비밀번호로 조회한다. 연락처는 받지 않고 알림도 없다.
- 학부모 회신은 받지 않는다. 교사는 여러 번 보낼 수 있다(추가 안내·정정).
- 4자리는 1만 가지뿐이라, 한 접수번호에 N번 틀리면 잠시 잠근다(잠금 중엔 맞는 번호도 거절).
"""

import re

import pytest

from tests.conftest import SCHOOL_ID, STUDENT_ID, TEST_PASSWORD

pytestmark = pytest.mark.api

SCHOOL = str(SCHOOL_ID)
ORDINARY = "아이가 친구와 다퉈서 상담을 받고 싶습니다. 확인 부탁드립니다."
ABUSIVE = "이 씨발 죽여버린다 가만 안 둬"
PIN = "4821"


def submit(client, pin=PIN, **extra):
    payload = {"schoolId": SCHOOL, "studentId": str(STUDENT_ID), "title": "상담 요청", "body": ORDINARY}
    if pin is not None:
        payload["pin"] = pin
    payload.update(extra)
    r = client.post("/api/complaints", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def lookup(client, code, pin=PIN):
    return client.post("/api/complaints/lookup", json={"receiptCode": code, "pin": pin})


def answer(client, headers, complaint_id, body="확인했습니다. 내일 상담 일정 안내드리겠습니다.", **extra):
    return client.post(f"/api/complaints/{complaint_id}/messages", headers=headers, json={"body": body, **extra})


# --- 접수번호 발급 -----------------------------------------------------------


def test_비밀번호를_주면_접수번호가_발급된다(client, student, assigned_teacher):
    r = submit(client)
    assert re.fullmatch(r"[A-Z2-9]{4}-[A-Z2-9]{4}", r["receiptCode"])


def test_비밀번호가_없으면_접수번호도_없다(client, student, assigned_teacher):
    assert submit(client, pin=None)["receiptCode"] is None


@pytest.mark.parametrize("pin", ["123", "12345", "abcd", "12a4"])
def test_비밀번호는_숫자_4자리만(client, student, pin):
    r = client.post("/api/complaints", json={"schoolId": SCHOOL, "body": ORDINARY, "pin": pin})
    assert r.status_code == 422


def test_비밀번호는_평문으로_저장하지_않는다(client, db, student, assigned_teacher):
    from app.models.complaint import Complaint

    r = submit(client)
    db.expire_all()
    c = db.get(Complaint, r["id"])
    assert c.lookup_pin_hash and PIN not in c.lookup_pin_hash


def test_접수번호는_매번_다르다(client, student, assigned_teacher):
    codes = {submit(client)["receiptCode"] for _ in range(4)}
    assert len(codes) == 4


# --- 비회원 조회 -------------------------------------------------------------


def test_접수번호와_비밀번호로_조회한다(client, student, assigned_teacher):
    r = submit(client)
    res = lookup(client, r["receiptCode"])
    assert res.status_code == 200
    body = res.json()
    assert body["body"] == ORDINARY and body["status"] == "pending_teacher" and body["answers"] == []


def test_접수번호는_대소문자_하이픈을_가리지_않는다(client, student, assigned_teacher):
    code = submit(client)["receiptCode"]
    assert lookup(client, code.lower().replace("-", " ")).status_code == 200


def test_조회_결과에_내부_정보가_없다(client, student, assigned_teacher):
    code = submit(client)["receiptCode"]
    keys = set(lookup(client, code).json())
    assert keys == {"receiptCode", "title", "body", "status", "createdAt", "updatedAt", "answers"}


def test_틀린_비밀번호와_없는_접수번호는_같은_응답(client, student, assigned_teacher):
    code = submit(client)["receiptCode"]
    wrong_pin = lookup(client, code, "0000")
    no_code = lookup(client, "ZZZZ-ZZZZ")
    assert wrong_pin.status_code == no_code.status_code == 404
    assert wrong_pin.json() == no_code.json(), "접수번호 존재 여부가 새면 안 된다"


def test_여러번_틀리면_잠기고_잠금중엔_맞는_번호도_거절(client, student, assigned_teacher, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "guest_lookup_max_failures", 3)
    code = submit(client)["receiptCode"]
    assert [lookup(client, code, "0000").status_code for _ in range(3)] == [404, 404, 404]
    res = lookup(client, code)  # 맞는 비밀번호
    assert res.status_code == 429, "잠금 중 맞는 번호를 통과시키면 대입이 막히지 않는다"
    assert "Retry-After" in res.headers


def test_잠금은_그_접수번호에만(client, student, assigned_teacher, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "guest_lookup_max_failures", 2)
    a = submit(client)["receiptCode"]
    b = submit(client)["receiptCode"]
    for _ in range(2):
        lookup(client, a, "0000")
    assert lookup(client, b).status_code == 200


def test_맞추면_실패_횟수가_초기화된다(client, student, assigned_teacher, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "guest_lookup_max_failures", 3)
    code = submit(client)["receiptCode"]
    lookup(client, code, "0000")
    lookup(client, code, "0000")
    assert lookup(client, code).status_code == 200
    lookup(client, code, "0000")
    lookup(client, code, "0000")
    assert lookup(client, code).status_code == 200, "초기화 안 되면 정상 사용자가 누적으로 잠긴다"


def test_잠금을_끌_수_있다(client, student, assigned_teacher, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "guest_lookup_max_failures", 0)
    code = submit(client)["receiptCode"]
    for _ in range(15):
        lookup(client, code, "0000")
    assert lookup(client, code).status_code == 200


# --- 교사 답변 ---------------------------------------------------------------


def test_교사가_답하면_학부모가_조회로_본다(client, student, tokens, assigned_teacher):
    r = submit(client)
    res = answer(client, tokens["teacher"], r["id"])
    assert res.status_code == 201, res.text

    view = lookup(client, r["receiptCode"]).json()
    assert view["status"] == "answered"
    assert [a["body"] for a in view["answers"]] == ["확인했습니다. 내일 상담 일정 안내드리겠습니다."]
    assert view["answers"][0]["senderLabel"] == "담당 선생님"


def test_학부모에게_교사_이름이나_계정은_나가지_않는다(client, student, tokens, assigned_teacher):
    r = submit(client)
    answer(client, tokens["teacher"], r["id"])
    a = lookup(client, r["receiptCode"]).json()["answers"][0]
    assert set(a) == {"body", "senderLabel", "createdAt"}


def test_여러번_보낼_수_있고_순서대로_보인다(client, student, tokens, assigned_teacher):
    r = submit(client)
    answer(client, tokens["teacher"], r["id"], body="첫 안내")
    answer(client, tokens["teacher"], r["id"], body="추가 안내")
    assert [a["body"] for a in lookup(client, r["receiptCode"]).json()["answers"]] == ["첫 안내", "추가 안내"]


def test_답변은_교직원_상세에도_보인다(client, student, tokens, assigned_teacher):
    r = submit(client)
    answer(client, tokens["teacher"], r["id"])
    detail = client.get(f"/api/complaints/{r['id']}", headers=tokens["teacher"]).json()
    assert detail["status"] == "answered"
    assert detail["messages"][0]["senderName"] == assigned_teacher.name


def test_배정되지_않은_교사는_답할_수_없다(client, student, tokens, users, assigned_teacher, db):
    from app.models.user import User

    other = User(school_id=SCHOOL_ID, role="teacher", email="other-t@test.sotong", name="다른 교사",
                 password_hash=users["teacher"].password_hash)
    db.add(other)
    db.commit()
    token = client.post("/api/auth/login", json={"email": "other-t@test.sotong", "password": TEST_PASSWORD})
    assert token.status_code == 200, token.text
    r = submit(client)
    res = answer(client, {"Authorization": f"Bearer {token.json()['accessToken']}"}, r["id"])
    assert res.status_code == 403


def test_학부모는_답변을_보낼_수_없다(client, student, tokens, assigned_teacher):
    r = submit(client)
    assert answer(client, tokens["parent"], r["id"]).status_code == 403


def test_비로그인은_답변을_보낼_수_없다(client, student, assigned_teacher):
    r = submit(client)
    assert client.post(f"/api/complaints/{r['id']}/messages", json={"body": "x"}).status_code == 401


def test_차단된_민원에는_답할_수_없다(client, student, tokens, assigned_teacher):
    r = submit(client, body=ABUSIVE)
    assert r["filtered"] is True
    assert answer(client, tokens["admin"], r["id"]).status_code == 409


def test_빈_답변은_거절(client, student, tokens, assigned_teacher):
    r = submit(client)
    assert answer(client, tokens["teacher"], r["id"], body="   ").status_code == 422


def test_초안을_고쳐_보내면_채택과_수정이_남는다(client, db, student, tokens, assigned_teacher):
    from app.models.complaint import AnswerDraft

    r = submit(client)
    draft = client.post(f"/api/complaints/{r['id']}/draft", headers=tokens["teacher"]).json()
    res = answer(client, tokens["teacher"], r["id"], body="고친 답변입니다.", draftId=draft["id"])
    assert res.status_code == 201
    db.expire_all()
    d = db.get(AnswerDraft, draft["id"])
    assert d.is_adopted and d.edited_body == "고친 답변입니다."


def test_자동응대로_빠졌던_민원도_답하면_답변완료(client, db, student, tokens, assigned_teacher):
    from app.models.complaint import Complaint

    r = submit(client)
    c = db.get(Complaint, r["id"])
    c.status, c.is_auto_handled = "auto_answered", True
    db.commit()
    answer(client, tokens["admin"], r["id"])
    db.expire_all()
    c = db.get(Complaint, r["id"])
    assert c.status == "answered" and c.is_auto_handled is False
