from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.complaint import AnswerDraft, Complaint
from app.models.user import User
from app.schemas.complaint import ComplaintCreate, ComplaintOut, DraftOut, Paginated
from app.services.ai import classify, draft_answer

router = APIRouter(prefix="/api/complaints", tags=["complaints"])


@router.post("", response_model=ComplaintOut, status_code=status.HTTP_201_CREATED)
def create_complaint(payload: ComplaintCreate, db: Session = Depends(get_db)):
    """학부모 민원 접수 → F1 자동 분류 → 상태 결정(라우팅).

    실제로는 여기서 F2(위험) · F3(욕설 필터)도 파이프라인으로 태워야 함.
    지금은 F1 분류만 연결한 최소 흐름.
    """
    result = classify(payload.body)

    complaint = Complaint(
        school_id=payload.school_id,
        student_id=payload.student_id,
        channel=payload.channel,
        title=payload.title,
        body=payload.body,
        category=result.category,
    )

    # 단순 행정은 챗봇 자동 응대 후보, 그 외는 교사 확인 대기
    if result.category == "administrative":
        complaint.status = "auto_answered"
        complaint.is_auto_handled = True
    else:
        complaint.status = "pending_teacher"

    db.add(complaint)
    db.commit()
    db.refresh(complaint)
    return complaint


@router.get("", response_model=Paginated)
def list_complaints(
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """교사 민원함 — 필터 통과분만. 교사면 본인 배정 건으로 제한."""
    stmt = select(Complaint).where(Complaint.filtered.is_(False))
    if current.role == "teacher":
        stmt = stmt.where(Complaint.assigned_teacher_id == current.id)

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    items = db.execute(
        stmt.order_by(Complaint.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()

    return Paginated(items=items, total=total, page=page, page_size=page_size)


@router.post("/{complaint_id}/draft", response_model=DraftOut)
def create_draft(
    complaint_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """F4: AI 답변 초안 생성."""
    complaint = db.get(Complaint, complaint_id)
    if complaint is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "민원을 찾을 수 없습니다.")

    body, model_name = draft_answer(complaint.body)
    draft = AnswerDraft(complaint_id=complaint.id, draft_body=body, model_name=model_name)
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft
