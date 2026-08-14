"""학부모 본인 민원 조회 - 라우트 등록 확인 테스트.

/mine 경로가 앱에 정상 등록되고, /{complaint_id}보다 먼저 매칭되도록
배치됐는지 확인한다. (경로 순서가 틀리면 mine이 complaint_id로 잡힘)
"""

from app.main import app


def test_mine_route_registered():
    """GET /api/complaints/mine 라우트가 등록되어 있어야 한다."""
    paths = [r.path for r in app.routes]
    assert "/api/complaints/mine" in paths


def test_mine_before_complaint_id():
    """/mine 이 /{complaint_id} 보다 먼저 등록되어야 한다."""
    paths = [r.path for r in app.routes]
    mine_idx = paths.index("/api/complaints/mine")
    detail_idx = paths.index("/api/complaints/{complaint_id}")
    assert mine_idx < detail_idx
