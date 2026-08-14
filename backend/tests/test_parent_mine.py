"""학부모 본인 민원함(`GET /api/complaints/mine`) — 라우트 배선 테스트.

두 가지를 고정한다. 둘 다 조용히 깨지는 종류라 눈으로는 못 잡는다.

1. **경로 순서** — `/mine` 이 `/{complaint_id}` 보다 먼저 등록되어야 한다.
   뒤에 있으면 "mine" 이 complaint_id 로 잡혀 404(또는 UUID 파싱 오류)가 난다.
2. **역할 제한** — 학부모 전용이어야 한다. 처음에는 `get_current_user` 만 걸려
   있어 교사 토큰으로도 200 이 나왔다. 지금은 빈 목록이 나올 뿐이지만, 대상
   범위가 흐려지면 나중에 필터 조건이 바뀔 때 남의 민원이 새어나갈 수 있다.

DB 없이 앱의 라우팅 테이블만 검사한다.
"""

import pytest
from fastapi import HTTPException

from app.api.deps import require_roles
from app.api.routes.complaints import parent_only, staff_only
from app.main import app

MINE_PATH = "/api/complaints/mine"
DETAIL_PATH = "/api/complaints/{complaint_id}"


def _route(path: str, method: str = "GET"):
    """경로 + 메서드로 라우트를 찾는다.

    `/api/complaints` 처럼 POST(접수)와 GET(목록)이 같은 경로를 쓰는 곳이 있어
    경로만으로 찾으면 엉뚱한 라우트를 검사하게 된다.
    """
    return next(
        r for r in app.routes
        if getattr(r, "path", None) == path and method in getattr(r, "methods", set())
    )


def _dependency_calls(path: str, method: str = "GET"):
    return [d.call for d in _route(path, method).dependant.dependencies]


class _FakeUser:
    def __init__(self, role: str):
        self.role = role


# --- 1. 경로 순서 -----------------------------------------------------------


def test_mine_라우트가_등록되어_있다():
    paths = [getattr(r, "path", None) for r in app.routes]
    assert MINE_PATH in paths


def test_mine_이_complaint_id_보다_먼저_매칭된다():
    paths = [getattr(r, "path", None) for r in app.routes]
    assert paths.index(MINE_PATH) < paths.index(DETAIL_PATH), (
        "뒤에 있으면 'mine' 이 complaint_id 로 잡힌다"
    )


# --- 2. 역할 제한 -----------------------------------------------------------


def test_mine_은_학부모_전용_가드를_쓴다():
    assert parent_only in _dependency_calls(MINE_PATH)


def test_mine_에_교직원_가드가_걸려_있지_않다():
    assert staff_only not in _dependency_calls(MINE_PATH)


def test_교사_민원함은_반대로_교직원_전용():
    """두 경로의 대상이 뒤바뀌지 않았는지 함께 고정한다."""
    calls = _dependency_calls("/api/complaints", "GET")
    assert staff_only in calls
    assert parent_only not in calls


def test_접수는_어떤_역할_가드도_걸지_않는다():
    """비로그인 접수를 막으면 안 된다(학부모에게 로그인을 강제하지 않는 설계)."""
    calls = _dependency_calls("/api/complaints", "POST")
    assert staff_only not in calls
    assert parent_only not in calls


# --- 가드 자체의 동작 -------------------------------------------------------


def test_학부모_가드는_학부모만_통과():
    guard = require_roles("parent")
    parent = _FakeUser("parent")
    assert guard(parent) is parent


@pytest.mark.parametrize("role", ["teacher", "admin", "mdt"])
def test_학부모_가드는_교직원을_403_으로_막는다(role):
    guard = require_roles("parent")
    with pytest.raises(HTTPException) as exc:
        guard(_FakeUser(role))
    assert exc.value.status_code == 403
