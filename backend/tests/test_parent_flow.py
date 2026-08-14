"""학부모 동선 — 민원 접수자 귀속 정책 테스트.

접수 경로(`POST /api/complaints`)는 **인증이 없다.** 학부모에게 앱 설치·로그인을
강제하지 않는 것이 이 서비스의 설계 결정이기 때문이다(project-overview §3).

그래서 "이 민원을 누가 냈는가"를 요청 본문에서 받으면 안 된다. 실제로 받고 있었고,
제3자가 임의의 학부모 id 를 넣어 접수하면 그 민원이 피해자의
`GET /api/complaints/mine` 에 나타났다. 학교폭력 신고를 남의 명의로 조작하는 것도
가능한 상태였다.

이제 귀속은 토큰에서만 결정한다(`deps.resolve_parent_id`). 여기서 그 정책을 고정한다.
"""

import uuid

import pytest

from app.api.deps import resolve_parent_id
from app.schemas.complaint import ComplaintCreate


class _FakeUser:
    """DB 없이 정책만 검사하기 위한 최소 대역."""

    def __init__(self, role: str):
        self.id = uuid.uuid4()
        self.role = role


# --- 귀속 정책 --------------------------------------------------------------


def test_로그인한_학부모는_본인에게_귀속():
    parent = _FakeUser("parent")
    assert resolve_parent_id(parent) == parent.id


def test_비로그인_접수는_익명():
    """로그인 없이도 접수는 되어야 한다 — 다만 귀속되지 않는다."""
    assert resolve_parent_id(None) is None


@pytest.mark.parametrize("role", ["teacher", "admin", "mdt"])
def test_교직원_계정으로_접수해도_학부모로_귀속되지_않는다(role):
    assert resolve_parent_id(_FakeUser(role)) is None


def test_귀속은_토큰_사용자_id_와_정확히_같다():
    """다른 사용자의 id 가 섞여 들어갈 여지가 없어야 한다."""
    a, b = _FakeUser("parent"), _FakeUser("parent")
    assert resolve_parent_id(a) == a.id
    assert resolve_parent_id(a) != b.id


# --- 입력 스키마 ------------------------------------------------------------


def test_접수_스키마는_parent_id_를_받지_않는다():
    """받아서 무시하는 대신 아예 없앤다 — 조용히 무시하면 프론트가 왜 귀속이
    안 되는지 알 수 없고, 신뢰할 수 없는 필드가 계약에 남는다."""
    assert "parent_id" not in ComplaintCreate.model_fields


def test_본문에_parent_id_를_넣어도_스키마가_무시한다():
    """구버전 클라이언트가 보내더라도 400 이 아니라 무시되어야 한다(하위호환)."""
    payload = ComplaintCreate.model_validate(
        {
            "schoolId": str(uuid.uuid4()),
            "parentId": str(uuid.uuid4()),  # 공격자가 넣은 값
            "body": "본인 확인용 민원",
        }
    )
    assert not hasattr(payload, "parent_id")


def test_필수값만으로_접수_가능():
    payload = ComplaintCreate(school_id=uuid.uuid4(), body="익명 민원")
    assert payload.student_id is None
