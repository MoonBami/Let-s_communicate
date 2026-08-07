"""F5: 유사 사례 지식베이스 관리.

사례를 등록하면 즉시 임베딩을 만들어 저장한다(등록 건수가 많아지면
`app.worker.tasks.index_case_embedding` 로 비동기 처리로 돌릴 수 있다).
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.case import ComplaintCase
from app.models.user import User
from app.schemas.case import CaseCreate, CaseOut
from app.services.ai import index_case

router = APIRouter(prefix="/api/cases", tags=["cases"])

# 지식베이스는 대응 기준이 되므로 등록·수정은 관리자·MDT 만.
_manager_only = require_roles("admin", "mdt")
_staff_only = require_roles("teacher", "admin", "mdt")


@router.post("", response_model=CaseOut, status_code=status.HTTP_201_CREATED)
def create_case(
    payload: CaseCreate,
    db: Session = Depends(get_db),
    _: User = Depends(_manager_only),
):
    case = ComplaintCase(
        source_complaint_id=payload.source_complaint_id,
        category=payload.category,
        summary=payload.summary,
        resolution=payload.resolution,
    )
    db.add(case)
    db.flush()  # case.id 확보 (임베딩 FK용)

    index_case(db, case)

    db.commit()
    db.refresh(case)
    return case


@router.get("", response_model=list[CaseOut])
def list_cases(
    category: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    _: User = Depends(_staff_only),
):
    stmt = select(ComplaintCase).order_by(ComplaintCase.created_at.desc()).limit(limit)
    if category is not None:
        stmt = stmt.where(ComplaintCase.category == category)
    return list(db.execute(stmt).scalars().all())
