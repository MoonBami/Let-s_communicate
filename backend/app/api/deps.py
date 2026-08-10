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


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    cred_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="인증이 필요합니다.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise cred_error
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise cred_error
    user = db.get(User, uuid.UUID(payload["sub"]))
    if user is None or not user.is_active:
        raise cred_error
    return user


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
