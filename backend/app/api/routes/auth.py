from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, SignupRequest, TokenOut, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])

# 회원가입 가능한 역할 — 학부모는 계정 없이 민원을 접수하는 설계라 제외.
_SIGNUP_ROLES = {"teacher", "admin"}


@router.post("/signup", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    """교사·관리자 회원가입 → 성공 시 바로 로그인 토큰 발급."""
    if payload.role not in _SIGNUP_ROLES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "회원가입은 교사 또는 관리자만 가능합니다.")

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
