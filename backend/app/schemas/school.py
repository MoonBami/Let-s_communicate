import uuid

from app.schemas.base import CamelModel


class SchoolPublicOut(CamelModel):
    """학교 코드 조회 결과 — 인증 없이 나가므로 **공개 정보만** 담는다.

    주소·전화·소속 교직원 등은 넣지 않는다. 학부모가 "내가 입력한 코드가 우리
    아이 학교가 맞는지" 확인하고 접수에 쓸 id 를 얻는 데 필요한 만큼이다.
    """

    id: uuid.UUID
    code: str
    name: str
    edu_office: str | None
