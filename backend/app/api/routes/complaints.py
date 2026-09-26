import logging

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import (
    can_view_filtered,
    client_ip,
    enforce_intake_rate_limit,
    get_current_user_optional,
    load_visible_complaint,
    require_roles,
    resolve_parent_id,
)
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
from app.services import audit
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

# 민원을 다루는 내부 사용자 — 학부모는 교사 민원함·상세엔 접근하지 않는다.
staff_only = require_roles("teacher", "admin", "mdt")

# 학부모 본인 민원함 전용. 교직원은 staff_only 경로로 조회하므로 여기 올 이유가 없고,
# 열어두면 "본인 것만 보이는 화면"의 대상 범위가 흐려진다.
parent_only = require_roles("parent")

# 위험도 순서 — 필터 심각도와 위험 분석 결과 중 높은 쪽을 채택할 때 사용.
_RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _max_risk(a: str, b: str) -> str:
    return a if _RISK_ORDER.get(a, 0) >= _RISK_ORDER.get(b, 0) else b


def screening_text(title: str | None, body: str) -> str:
    """AI 파이프라인(F3·F1·F2·게이트)이 검사할 텍스트.

    **제목도 반드시 포함해야 한다.** 한때 본문만 검사해서, 제목에 욕설·위협을 쓰면
    필터를 그대로 통과해 교사 민원함에 떴다. 교사가 목록에서 가장 먼저 읽는 자리가
    무방비였고, 차단되지 않으니 증거(`content_filter_logs`)도 남지 않았다.

    제목만 따로 검사하지 않고 **본문과 합쳐서 한 번에** 보는 이유는 맥락 때문이다.
    제목은 짧아 맥락이 없다 — "때려서" 같은 신고 표현이 단독으로 들어오면 가해와
    구분할 근거가 사라져 오차단이 늘어난다(F3 오차단 10종 수정 이력 참고).
    합쳐서 보면 제목의 표현도 잡히면서 본문의 맥락이 유지된다.
    """
    title = (title or "").strip()
    return f"{title}\n{body}" if title else body


@router.post(
    "",
    response_model=ComplaintOut,
    status_code=status.HTTP_201_CREATED,
    # 인증이 없는 공개 엔드포인트라 유량 제한이 유일한 방어선이다.
    dependencies=[Depends(enforce_intake_rate_limit)],
)
def create_complaint(
    payload: ComplaintCreate,
    db: Session = Depends(get_db),
    current: User | None = Depends(get_current_user_optional),
):
    """학부모 민원 접수 → AI 게이트웨이 파이프라인.

    로그인 없이도 접수할 수 있다(학부모에게 앱·로그인을 강제하지 않는 설계).
    로그인한 학부모의 접수만 본인에게 귀속되며, **귀속 대상은 토큰에서만
    결정한다** — 요청 본문으로 받으면 남의 명의로 민원을 넣을 수 있다.

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
    screened = screening_text(payload.title, body)  # 제목까지 함께 검사한다

    filter_result = filter_content(screened)   # F3
    classification = classify(screened)        # F1
    risk_result = analyze_risk(screened)       # F2
    gate = evaluate_auto_answer(               # 자동 응대 안전장치
        screened, classification.category, classification.confidence, risk_result.risk
    )

    complaint = Complaint(
        school_id=payload.school_id,
        parent_id=resolve_parent_id(current),  # 본문이 아니라 토큰에서
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
                # 제목+본문 전체를 증거로 남긴다. 본문만 남기면 제목에 쓴 욕설이
                # 기록에서 사라져, 차단은 됐는데 근거가 없는 상태가 된다.
                raw_evidence=screened,  # (접근 통제·암호화는 저장 계층 책임)
            )
        )

    db.commit()
    db.refresh(complaint)
    return complaint


@router.get("/mine", response_model=Paginated)
def list_my_complaints(
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current: User = Depends(parent_only),
):
    """학부모 본인 민원함 — `parent_id` 가 본인인 민원만. 차단 민원은 제외.

    귀속은 접수 시 토큰에서 결정되므로(`deps.resolve_parent_id`) 여기 보이는
    민원은 본인이 로그인 상태로 접수한 것뿐이다. 비로그인 접수는 익명이라
    여기 나타나지 않는다.
    """
    stmt = select(Complaint).where(
        Complaint.parent_id == current.id,
        Complaint.filtered.is_(False),
    )
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    items = db.execute(
        stmt.order_by(Complaint.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()
    return Paginated(items=items, total=total, page=page, page_size=page_size)


@router.get("", response_model=Paginated)
def list_complaints(
    request: Request,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current: User = Depends(staff_only),
):
    """민원 목록 — 역할에 따라 보이는 범위가 다르다.

    - 교사: 본인에게 배정된, 필터를 통과한 민원만
    - admin·mdt: 차단된 민원(F3 증거)까지 전부. 증거를 찾을 화면이 여기뿐이므로
      목록에서 빼면 UUID 를 아는 경우 말고는 도달할 수 없다(상세와 같은 규칙).

    차단 건은 `status=filtered_blocked` / `filtered=true` 로 구분되므로 목록에서
    섞여 보여도 화면에서 식별된다.
    """
    stmt = select(Complaint)
    if not can_view_filtered(current.role):
        stmt = stmt.where(Complaint.filtered.is_(False))
    if current.role == "teacher":
        stmt = stmt.where(Complaint.assigned_teacher_id == current.id)

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    items = db.execute(
        stmt.order_by(Complaint.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()

    # 목록 미리보기에도 차단 민원의 원문이 실려 나가므로 증거 접근으로 기록한다.
    # 건별로 남기면 목록 한 번에 로그가 여러 줄 쌓이므로 요청당 1줄 + 건수로 남긴다.
    blocked_count = sum(1 for item in items if item.filtered)
    if blocked_count:
        audit.record(
            db,
            user_id=current.id,
            action=audit.LIST_BLOCKED_COMPLAINTS,
            entity_type="complaint",
            ip_address=client_ip(request),
            detail={"role": current.role, "blocked_count": blocked_count, "page": page},
        )

    return Paginated(items=items, total=total, page=page, page_size=page_size)


@router.get("/{complaint_id}", response_model=ComplaintDetail)
def get_complaint(
    complaint_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(staff_only),
):
    """민원 상세 — 최신 분류·위험 분석 포함."""
    complaint = load_visible_complaint(db, complaint_id, current, request)

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
    request: Request,
    limit: int = 3,
    db: Session = Depends(get_db),
    current: User = Depends(staff_only),
):
    """F5: 이 민원과 유사한 과거 사례·대응 방식."""
    complaint = load_visible_complaint(db, complaint_id, current, request)
    found = search_similar_cases(db, complaint.body, limit=limit, category=complaint.category)
    return [SimilarCaseOut.model_validate(c) for c in found]


@router.post("/{complaint_id}/draft", response_model=DraftOut)
def create_draft(
    complaint_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(staff_only),
):
    """F4: AI 답변 초안 생성 — F5로 찾은 유사 사례를 근거로 주입한다."""
    complaint = load_visible_complaint(db, complaint_id, current, request)

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
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(staff_only),
):
    """이 민원에 대해 생성된 답변 초안 이력."""
    complaint = load_visible_complaint(db, complaint_id, current, request)
    drafts = db.execute(
        select(AnswerDraft)
        .where(AnswerDraft.complaint_id == complaint.id)
        .order_by(AnswerDraft.created_at.desc())
    ).scalars().all()
    return list(drafts)
