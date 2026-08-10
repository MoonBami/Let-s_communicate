"""audit_logs 감사 로그 기록 테스트 (간단 버전).

AuditLog 모델로 감사 로그를 DB에 남기고, 다시 조회했을 때
기록이 정확히 저장되는지 확인한다. (차단 민원 열람 추적의 핵심)
"""

from app.db.session import SessionLocal
from app.models.analysis import AuditLog


def test_audit_log_is_saved():
    """감사 로그를 저장하면 DB에서 다시 읽을 수 있어야 한다."""
    db = SessionLocal()
    try:
        log = AuditLog(
            action="VIEW_BLOCKED_COMPLAINT",
            entity_type="complaint",
        )
        db.add(log)
        db.commit()
        db.refresh(log)

        saved = db.get(AuditLog, log.id)
        assert saved is not None
        assert saved.action == "VIEW_BLOCKED_COMPLAINT"
        assert saved.entity_type == "complaint"
        assert saved.created_at is not None

        # 정리: 테스트가 남긴 로그 삭제
        db.delete(saved)
        db.commit()
    finally:
        db.close()
