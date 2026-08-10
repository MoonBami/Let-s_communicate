import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import load_visible_complaint, require_roles
from app.db.session import get_db
from app.models.analysis import Classification, ContentFilterLog, RiskAnalysis
from app.models.complaint import AnswerDraft, Complaint
from app.models.user import User
from app.schemas.case import SimilarCaseOut
from app.schemas.complaint import (
    ClassificationOut,
    ComplaintCreate,
    ComplaintDetail,
    ComplaintOut,
    DraftOut,
    Paginated,
    RiskOut,
)
from app.services.ai import (
    analyze_risk,
    classify,
    draft_answer,
    evaluate_auto_answer,
    filter_content,
    route_teacher,
    search_similar_cases,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/complaints", tags=["complaints"])

# 민원을 다루는 내부 사용자 — 학부모는 접수만 하고 민원함·상세엔 접근하지 않는다.
staff_only = require_roles("teacher", "admin", "mdt")

# 위험도 순서 — 필터 심각도와 위험 분석 결과 중 높은 쪽을 채택할 때 사용.
_RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _max_risk(a: str, b: str) -> str:
    return a if _RISK_ORDER.get(a, 0) >= _RISK_ORDER.get(b, 0) else b


@router.post("", response_model=ComplaintOut, status_code=status.HTTP_201_CREATED)
def create_complaint(payload: ComplaintCreate, db: Session = Depends(get_db)):
    """학부모 민원 접수 → AI 게이트웨이 파이프라인.

    F3(욕설·위협 필터) → F1(분류) → F2(위험) → 자동응대 게이트 → 라우팅 순으로
    태운 뒤 상태를 정한다.
    - 욕설·위협 차단: 교사 미노출, 원문을 증거로 보관(status=filtered_blocked).
    - 단순 행정 + 게이트 통과: 챗봇 자동 응대 후보(status=auto_answered).
    - 그 외 전부: 담당 교사 자동 배정(status=pending_teacher).

    게이트를 통과하지 못한 단순 행정도 교사에게 간다 — AI 판단이 틀렸을 때
    민원이 사라지는 것보다 교사가 한 번 더 보는 편이 낫다(services/ai/gate.py).
    분류·위험 결과는 이력 테이블에 함께 남긴다.
    """
    body = payload.body

    filter_result = filter_content(body)       # F3
    classification = classify(body)            # F1
    risk_result = analyze_risk(body)           # F2
    gate = evaluate_auto_answer(               # 자동 응대 안전장치
        body, classification.category, classification.confidence, risk_result.risk
    )

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
        # 위협성 → 차단 + 증거. 교사에게 넘기지 않는다.
        complaint.status = "filtered_blocked"
        complaint.filtered = True
        complaint.risk = _max_risk(complaint.risk, filter_result.severity)
    elif gate.can_auto_answer:
        # 단순 행정 + 게이트 통과 → 챗봇 자동 응대 후보
        complaint.status = "auto_answered"
        complaint.is_auto_handled = True
    else:
        # 게이트 미통과분 포함 → 담당 교사 자동 배정
        complaint.status = "pending_teacher"
        complaint.assigned_teacher_id = route_teacher(db, payload.student_id)
        if classification.category == "administrative":
            # 자동 응대될 수 있었으나 안전장치가 막은 건 — 임계값 조정 근거로 남긴다.
            logger.info("자동 응대 보류 → 교사 배정: %s", gate.reason)

    db.add(complaint)
    db.flush()  # complaint.id 확보 (자식 레코드 FK용)

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
                raw_evidence=body,  # 원문 증거 (접근 통제·암호화는 저장 계층 책임)
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
    current: User = Depends(staff_only),
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
    current: User = Depends(staff_only),
):
    """민원 상세 — 최신 분류·위험 분석 포함."""
    complaint = load_visible_complaint(db, complaint_id, current)

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


@router.get("/{complaint_id}/similar-cases", response_model=list[SimilarCaseOut])
def similar_cases(
    complaint_id: str,
    limit: int = 3,
    db: Session = Depends(get_db),
    current: User = Depends(staff_only),
):
    """F5: 이 민원과 유사한 과거 사례·대응 방식."""
    complaint = load_visible_complaint(db, complaint_id, current)
    found = search_similar_cases(db, complaint.body, limit=limit, category=complaint.category)
    return [SimilarCaseOut.model_validate(c) for c in found]


@router.post("/{complaint_id}/draft", response_model=DraftOut)
def create_draft(
    complaint_id: str,
    db: Session = Depends(get_db),
    current: User = Depends(staff_only),
):
    """F4: AI 답변 초안 생성 — F5로 찾은 유사 사례를 근거로 주입한다."""
    complaint = load_visible_complaint(db, complaint_id, current)

    cases = search_similar_cases(db, complaint.body, category=complaint.category)
    body, model_name = draft_answer(
        complaint.body,
        similar_cases=[c.as_prompt_line() for c in cases],
    )

    draft = AnswerDraft(complaint_id=complaint.id, draft_body=body, model_name=model_name)
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft


@router.get("/{complaint_id}/drafts", response_model=list[DraftOut])
def list_drafts(
    complaint_id: str,
    db: Session = Depends(get_db),
    current: User = Depends(staff_only),
):
    """이 민원에 대해 생성된 답변 초안 이력."""
    complaint = load_visible_complaint(db, complaint_id, current)
    drafts = db.execute(
        select(AnswerDraft)
        .where(AnswerDraft.complaint_id == complaint.id)
        .order_by(AnswerDraft.created_at.desc())
    ).scalars().all()
    return list(drafts)
