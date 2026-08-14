"""감사 로그 기록 — 민감정보 접근 추적.

차단된 민원(F3 증거)의 원문에는 욕설·위협이 그대로 담겨 있고, 학생·학부모에 관한
민감정보가 섞여 있다. 이걸 **누가 언제 열람했는지 남기는 것**은 기획 문서가
필수로 꼽은 요건이다(README 법적·보안·윤리 §개인정보).

## 실패 처리 — 열람을 막지 않는다

감사 기록에 실패하면 **경고만 남기고 열람은 통과시킨다.** 감사 로그 저장 문제로
관리자가 증거에 접근하지 못하면, 정작 대응해야 할 사안 처리가 멈춘다.

다만 이건 정책 판단이다. "감사 기록이 남지 않으면 열람도 불가"를 요구하는 규정도
있으므로(접근 통제를 감사와 묶는 설계), 운영 전환 시 법률 검토가 필요하다.
바꾸려면 이 함수에서 예외를 올리면 된다.
"""

from __future__ import annotations

import ipaddress
import logging
import uuid

from sqlalchemy.orm import Session

from app.models.analysis import AuditLog

logger = logging.getLogger(__name__)


def _normalize_ip(value: str | None) -> tuple[str | None, str | None]:
    """returns (INET 에 넣을 값, detail 에 남길 원본)

    `audit_logs.ip_address` 는 `INET` 이라 IP 형식이 아니면 INSERT 자체가 실패한다.
    그런데 실패는 fail-open 으로 삼켜지므로 **감사 로그가 조용히 사라진다** —
    실제로 그랬다(TestClient 가 주는 "testclient" 로 전 건이 유실됐다).
    프록시 설정 오류로 호스트명이 들어오는 경우에도 같은 일이 생긴다.

    그래서 형식을 확인해 유효하지 않으면 컬럼은 비우고 원본은 detail 에 남긴다.
    """
    if not value:
        return None, None
    try:
        return str(ipaddress.ip_address(value)), None
    except ValueError:
        return None, value

# action 값. schema.sql 주석의 예시(VIEW_RECORDING / EXPORT_EVIDENCE)와 같은 계열.
VIEW_BLOCKED_COMPLAINT = "VIEW_BLOCKED_COMPLAINT"
LIST_BLOCKED_COMPLAINTS = "LIST_BLOCKED_COMPLAINTS"


def record(
    db: Session,
    *,
    user_id: uuid.UUID | None,
    action: str,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    ip_address: str | None = None,
    detail: dict | None = None,
) -> None:
    """감사 로그 1건을 남긴다. 실패해도 예외를 올리지 않는다(위 설명 참고).

    호출부의 트랜잭션과 분리해 즉시 커밋한다 — 뒤이은 처리가 롤백되어도
    '열람했다'는 사실 자체는 남아야 한다.
    """
    inet, raw_source = _normalize_ip(ip_address)
    if raw_source is not None:
        # IP 형식이 아니면 컬럼엔 못 넣지만 추적 단서는 남긴다.
        detail = {**(detail or {}), "source": raw_source}

    try:
        db.add(
            AuditLog(
                user_id=user_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                ip_address=inet,
                detail=detail,
            )
        )
        db.commit()
    except Exception:
        logger.exception(
            "audit | 기록 실패 → 열람은 계속 진행한다 action=%s entity=%s/%s",
            action, entity_type, entity_id,
        )
        db.rollback()
