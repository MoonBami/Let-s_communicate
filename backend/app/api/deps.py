import uuid
from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.complaint import Complaint
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def _user_from_token(token: str | None, db: Session) -> User | None:
    """토큰에서 사용자를 복원. 실패 사유를 구분하지 않고 None 을 돌려준다.

    `sub` 가 UUID 형식이 아닐 수 있으므로(위조·구버전 토큰) 변환 실패도
    인증 실패로 처리한다 — 500 이 아니라 401 이 되도록.
    """
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        return None
    try:
        user_id = uuid.UUID(str(payload["sub"]))
    except (ValueError, TypeError):
        return None
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        return None
    return user


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    user = _user_from_token(token, db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증이 필요합니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_current_user_optional(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    """토큰이 있으면 사용자, 없거나 유효하지 않으면 None.

    비로그인 접수를 허용하는 경로(민원 접수)에서 쓴다. 인증 실패를 오류로
    만들지 않되, **유효하지 않은 토큰을 '로그인한 것'으로 취급하지도 않는다.**
    """
    return _user_from_token(token, db)


def resolve_parent_id(current: User | None) -> uuid.UUID | None:
    """민원 접수자(학부모) 식별 — **반드시 토큰에서만 온다.**

    요청 본문의 parent_id 를 신뢰하면 제3자가 임의의 학부모 명의로 민원을
    넣을 수 있다. 접수 경로는 인증이 없으므로(학부모에게 로그인을 강제하지
    않는 설계) 본문 값은 아무나 채울 수 있기 때문이다. 실제로 가능했다 —
    타인의 id 로 넣은 민원이 그 사람의 `/api/complaints/mine` 에 나타났다.

    로그인하지 않은 접수는 익명(None)으로 남는다. 학부모·교직원이 아닌
    역할로 로그인한 경우에도 귀속시키지 않는다.
    """
    if current is not None and current.role == "parent":
        return current.id
    return None


def require_roles(*roles: str) -> Callable[[User], User]:
    """지정한 역할만 통과시키는 의존성 팩토리.

    토큰의 role 클레임이 아니라 **DB 의 현재 역할**로 판정한다(토큰 발급 후
    역할이 변경·정지된 계정이 예전 권한을 유지하지 못하도록).
    """
    allowed = set(roles)

    def guard(current: User = Depends(get_current_user)) -> User:
        if current.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "이 작업을 수행할 권한이 없습니다.")
        return current

    return guard


# 차단된 민원(F3 증거)을 열람할 수 있는 역할.
# 목록과 상세가 **같은 규칙**을 써야 한다 — 상세는 허용하는데 목록에서 빼면
# 관리자가 UUID 를 이미 아는 경우 말고는 증거에 도달할 수 없다(실제로 그랬다).
EVIDENCE_ROLES = ("admin", "mdt")


def can_view_filtered(role: str) -> bool:
    """차단된 민원(증거)을 열람할 수 있는 역할인가."""
    return role in EVIDENCE_ROLES


def load_visible_complaint(db: Session, complaint_id: str, current: User) -> Complaint:
    """열람 권한을 확인하고 민원을 반환.

    - 차단된 민원(증거)은 admin·mdt 만 열람 가능 — 교사에겐 애초에 노출하지 않는다.
    - 교사는 본인에게 배정된 민원만 열람 가능.
    """
    complaint = db.get(Complaint, complaint_id)
    if complaint is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "민원을 찾을 수 없습니다.")

    if complaint.filtered and not can_view_filtered(current.role):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "열람 권한이 없습니다.")
    if current.role == "teacher" and complaint.assigned_teacher_id != current.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "본인에게 배정된 민원만 열람할 수 있습니다.")

    return complaint
