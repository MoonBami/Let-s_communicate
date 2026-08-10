"""민원 가시성 규칙 테스트.

"누가 차단된 민원(F3 증거)을 볼 수 있나" 는 목록(`GET /api/complaints`)과
상세(`GET /api/complaints/{id}`)가 **같은 규칙**을 써야 한다.

실제로 어긋난 적이 있다: 상세는 admin·mdt 에게 허용하면서 목록은 역할과 무관하게
차단 건을 전부 제외했다. 그 결과 관리자가 증거에 도달할 방법이 'UUID 를 이미
아는 경우' 뿐이었다 — F3 가 증거를 보관해도 찾을 화면이 없었다.

그래서 규칙을 `deps.can_view_filtered` 한 곳으로 모으고 여기서 고정한다.
"""

import pytest

from app.api.deps import EVIDENCE_ROLES, can_view_filtered
from app.models._enums import _USER_ROLE


@pytest.mark.parametrize("role", ["admin", "mdt"])
def test_관리자와_민원대응팀은_증거를_본다(role):
    assert can_view_filtered(role), f"{role} 이 증거에 도달할 수 없으면 F3 보관이 무의미하다"


@pytest.mark.parametrize("role", ["teacher", "parent"])
def test_교사와_학부모는_증거를_못_본다(role):
    assert not can_view_filtered(role)


def test_모든_역할이_판정된다():
    """새 역할이 추가되면 여기서 걸려 판단을 강제한다."""
    assert set(_USER_ROLE) == {"teacher", "parent", "admin", "mdt"}, (
        "역할이 추가·변경되었다. 차단 민원 열람 허용 여부를 명시적으로 정할 것"
    )


def test_증거_열람_역할_목록이_예상과_같다():
    assert set(EVIDENCE_ROLES) == {"admin", "mdt"}


def test_알_수_없는_역할은_거부():
    """오타·미래 역할이 조용히 통과하지 않도록 기본은 거부."""
    for role in ("", "ADMIN", "superuser", "principal", None):
        assert not can_view_filtered(role)  # type: ignore[arg-type]
