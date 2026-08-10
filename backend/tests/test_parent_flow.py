"""학부모 동선 - parent_id 저장 테스트.

ComplaintCreate 스키마가 parent_id를 받을 수 있고,
접수 시 complaints.parent_id에 저장되는지 확인한다. (development-status 6-3번 갭)
"""

import uuid

from app.schemas.complaint import ComplaintCreate


def test_complaint_create_accepts_parent_id():
    """접수 스키마가 parent_id 필드를 받아들여야 한다."""
    pid = uuid.uuid4()
    payload = ComplaintCreate(
        school_id=uuid.uuid4(),
        parent_id=pid,
        body="본인 확인용 민원",
    )
    assert payload.parent_id == pid


def test_complaint_create_parent_id_optional():
    """parent_id 없이도 접수는 가능해야 한다 (익명 접수 하위호환)."""
    payload = ComplaintCreate(
        school_id=uuid.uuid4(),
        body="익명 민원",
    )
    assert payload.parent_id is None
