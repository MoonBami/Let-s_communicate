from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.complaint import Complaint
from app.models.user import User

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

# F9는 관리자 통계 — 교사 개인 업무 화면이 아니라 관리자·MDT 전용.
_manager_only = require_roles("admin", "mdt")


class StatRow(BaseModel):
    category: str | None
    risk: str
    status: str
    day: str
    total: int


@router.get("/stats", response_model=list[StatRow])
def stats(db: Session = Depends(get_db), _: User = Depends(_manager_only)):
    """F9: 카테고리·위험도·상태·일자별 집계 (v_complaint_stats 뷰와 동등)."""
    day = func.date_trunc("day", Complaint.created_at)
    rows = db.execute(
        select(
            Complaint.category,
            Complaint.risk,
            Complaint.status,
            day.label("day"),
            func.count().label("total"),
        ).group_by(Complaint.category, Complaint.risk, Complaint.status, day)
    ).all()

    return [
        StatRow(
            category=r.category,
            risk=r.risk,
            status=r.status,
            day=r.day.date().isoformat() if r.day else "",
            total=r.total,
        )
        for r in rows
    ]
