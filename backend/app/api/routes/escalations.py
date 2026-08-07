"""F8: 민원대응팀(MDT) 이관.

교사가 단독 대응하기 어려운 민원을 관리자·MDT로 넘긴다. 이관 이력은
'정당한 민원을 AI가 오차단하지 않도록' 두는 사람 재검토 경로이기도 하다.

민원 상태 연동:
    이관 요청 → escalated
    해결(resolved) → closed (+closed_at)
    반송(rejected) → pending_teacher (교사가 다시 처리)
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import load_visible_complaint, require_roles
from app.db.session import get_db
from app.models.complaint import Complaint
from app.models.escalation import Escalation
from app.models.user import User
from app.schemas.escalation import EscalationCreate, EscalationOut, EscalationUpdate

router = APIRouter(prefix="/api/escalations", tags=["escalations"])

# 이관 요청은 담당 교사(또는 관리자)가, 접수·처리는 관리자·MDT 가 한다.
_requester_only = require_roles("teacher", "admin")
_handler_only = require_roles("admin", "mdt")

# 아직 종결되지 않은 이관 — 같은 민원에 중복 요청을 막는 기준.
_OPEN_STATUSES = ("requested", "accepted")
_CLOSING_STATUSES = ("resolved", "rejected")


@router.post("", response_model=EscalationOut, status_code=status.HTTP_201_CREATED)
def request_escalation(
    payload: EscalationCreate,
    db: Session = Depends(get_db),
    current: User = Depends(_requester_only),
):
    complaint = load_visible_complaint(db, str(payload.complaint_id), current)

    open_existing = db.execute(
        select(Escalation).where(
            Escalation.complaint_id == complaint.id,
            Escalation.status.in_(_OPEN_STATUSES),
        )
    ).scalar_one_or_none()
    if open_existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "이미 진행 중인 이관 요청이 있습니다.")

    escalation = Escalation(
        complaint_id=complaint.id,
        requested_by=current.id,
        reason=payload.reason,
    )
    complaint.status = "escalated"

    db.add(escalation)
    db.commit()
    db.refresh(escalation)
    return escalation


@router.get("", response_model=list[EscalationOut])
def list_escalations(
    status_filter: str | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
    _: User = Depends(_handler_only),
):
    """이관 목록 — 관리자·MDT 전용. `?status=` 로 상태별 조회."""
    stmt = select(Escalation).order_by(Escalation.created_at.desc())
    if status_filter is not None:
        stmt = stmt.where(Escalation.status == status_filter)
    return list(db.execute(stmt).scalars().all())


@router.patch("/{escalation_id}", response_model=EscalationOut)
def update_escalation(
    escalation_id: str,
    payload: EscalationUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(_handler_only),
):
    if payload.status not in ("accepted", *_CLOSING_STATUSES):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "status 는 accepted / resolved / rejected 중 하나여야 합니다.",
        )

    escalation = db.get(Escalation, escalation_id)
    if escalation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "이관 요청을 찾을 수 없습니다.")
    if escalation.status in _CLOSING_STATUSES:
        raise HTTPException(status.HTTP_409_CONFLICT, "이미 종결된 이관 요청입니다.")

    escalation.status = payload.status
    escalation.assigned_to = current.id
    if payload.resolution is not None:
        escalation.resolution = payload.resolution

    if payload.status in _CLOSING_STATUSES:
        now = datetime.now(timezone.utc)
        escalation.resolved_at = now
        complaint = db.get(Complaint, escalation.complaint_id)
        if payload.status == "resolved":
            complaint.status = "closed"
            complaint.closed_at = now
        else:
            complaint.status = "pending_teacher"

    db.commit()
    db.refresh(escalation)
    return escalation
