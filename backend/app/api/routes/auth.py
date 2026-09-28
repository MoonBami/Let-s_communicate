from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, SignupRequest, TokenOut, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])

# 회원가입 가능한 역할 — **교사만.**
#
# 관리자는 여기서 만들 수 없다. 전에는 {"teacher", "admin"} 이어서 누구나 가입 화면에서
# 역할을 '관리자'로 골라 차단된 민원(욕설·위협 원문 증거)까지 전부 열람할 수 있었다.
# 관리자 계정은 seed.py 또는 운영자가 DB 에서 직접 만든다.
#
# 교사로 가입해도 **그 자체로는 아무 민원도 보이지 않는다.** 관리자가 학년·반을
# 배정해야 라우팅 대상이 된다(routes/admin.py). 가입은 공개 경로라서 "나는 3학년
# 2반 담임"이라는 본인 주장을 믿고 바로 배정하면 아무나 그 반 민원을 읽게 된다.
# 학부모는 계정 없이 민원을 접수하는 설계라 제외.
_SIGNUP_ROLES = {"teacher"}


@router.post("/signup", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    """교사·관리자 회원가입 → 성공 시 바로 로그인 토큰 발급."""
    if payload.role not in _SIGNUP_ROLES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "회원가입은 교사 계정만 가능합니다. 관리자 계정은 운영자에게 요청해 주세요.")

    exists = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "이미 가입된 이메일입니다.")

    user = User(
        role=payload.role,
        email=payload.email,
        name=payload.name,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(str(user.id), extra={"role": user.role})
    return TokenOut(access_token=token)


@router.post("/login", response_model=TokenOut)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if not user or not user.password_hash or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "이메일 또는 비밀번호가 올바르지 않습니다.")
    token = create_access_token(str(user.id), extra={"role": user.role})
    return TokenOut(access_token=token)


@router.get("/me", response_model=UserOut)
def me(current: User = Depends(get_current_user)):
    return current
