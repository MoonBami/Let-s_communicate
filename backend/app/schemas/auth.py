import uuid

from pydantic import EmailStr, Field

from app.schemas.base import CamelModel


class LoginRequest(CamelModel):
    email: EmailStr
    password: str


class SignupRequest(CamelModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str = Field(min_length=1)
    role: str = "teacher"  # teacher 만 허용 (라우트에서 검증)


class TokenOut(CamelModel):
    access_token: str  # → accessToken
    token_type: str = "bearer"  # → tokenType


class UserOut(CamelModel):
    id: uuid.UUID
    school_id: uuid.UUID | None
    role: str
    email: str | None
    name: str
    is_active: bool
