from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.analysis import AuditLog, Classification, ContentFilterLog, RiskAnalysis
from app.models.complaint import AnswerDraft, Complaint
from app.models.user import User
from app.schemas.complaint import (
    ClassificationOut,
    ComplaintCreate,
    ComplaintDetail,
    ComplaintOut,
    DraftOut,
    Paginated,
    RiskOut,
)
from app.services.ai import analyze_risk, classify, draft_answer, filter_content, route_teacher

router = APIRouter(prefix="/api/complaints", tags=["complaints"])

# 위험도 순서 — 필터 심각도와 위험 분석 결과 중 높은 쪽을 채택할 때 사용.
_RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _max_risk(a: str, b: str) -> str:
    return a if _RISK_ORDER.get(a, 0) >= _RISK_ORDER.get(b, 0) else b


@router.post("", response_model=ComplaintOut, status_code=status.HTTP_201_CREATED)
def create_complaint(payload: ComplaintCreate, db: Session = Depends(get_db)):
    """학부모 민원 접수 → AI 게이트웨이 파이프라인.

    F3(욕설·위협 필터) → F1(분류) → F2(위험) → 라우팅 순으로 태운 뒤 상태를 정한다.
    """
    body = payload.body

    filter_result = filter_content(body)       # F3
    classification = classify(body)            # F1
    risk_result = analyze_risk(body)           # F2

    complaint = Complaint(
        school_id=payload.school_id,
        student_id=payload.student_id,
        channel=payload.channel,
        title=payload.title,
        body=body,
        category=classification.category,
        risk=risk_result.risk,
    )

    if filter_result.is_blocked:
        complaint.status = "filtered_blocked"
        complaint.filtered = True
        complaint.risk = _max_risk(complaint.risk, filter_result.severity)
    elif classification.category == "administrative":
        complaint.status = "auto_answered"
        complaint.is_auto_handled = True
    else:
        complaint.status = "pending_teacher"
        complaint.assigned_teacher_id = route_teacher(db, payload.student_id)

    db.add(complaint)
    db.flush()

    db.add(
        Classification(
            complaint_id=complaint.id,
            predicted=classification.category,
            confidence=classification.confidence,
            model_name=classification.model_name,
            is_auto_routed=complaint.assigned_teacher_id is not None,
        )
    )
    db.add(
        RiskAnalysis(
            complaint_id=complaint.id,
            sentiment_score=risk_result.sentiment_score,
            aggression_score=risk_result.aggression_score,
            risk=risk_result.risk,
            reasons=risk_result.reasons,
            model_name=risk_result.model_name,
        )
    )
    if filter_result.is_blocked:
        db.add(
            ContentFilterLog(
                complaint_id=complaint.id,
                is_blocked=True,
                matched_terms=filter_result.matched_terms,
                severity=filter_result.severity,
                raw_evidence=body,
            )
        )

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


@router.get("/{complaint_id}", response_model=ComplaintDetail)
def get_complaint(
    complaint_id: str,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """민원 상세 — 최신 분류·위험 분석 포함.

    차단된 민원(증거)은 admin·mdt 만 열람 가능. 교사에겐 노출되지 않는다.
    """
    complaint = db.get(Complaint, complaint_id)
    if complaint is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "민원을 찾을 수 없습니다.")

    if complaint.filtered and current.role not in ("admin", "mdt"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "열람 권한이 없습니다.")

    # 차단 민원(증거) 열람 시 감사 로그 기록 (누가·언제·무엇을)
    if complaint.filtered:
        db.add(
            AuditLog(
                user_id=current.id,
                action="VIEW_BLOCKED_COMPLAINT",
                entity_type="complaint",
                entity_id=complaint.id,
            )
        )
        db.commit()

    latest_cls = db.execute(
        select(Classification)
        .where(Classification.complaint_id == complaint.id)
        .order_by(Classification.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    latest_risk = db.execute(
        select(RiskAnalysis)
        .where(RiskAnalysis.complaint_id == complaint.id)
        .order_by(RiskAnalysis.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    detail = ComplaintDetail.model_validate(complaint)
    if latest_cls is not None:
        detail.classification = ClassificationOut.model_validate(latest_cls)
    if latest_risk is not None:
        detail.risk_analysis = RiskOut.model_validate(latest_risk)
    return detail


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
