"""학교 코드 조회 — 학부모 민원 접수 화면의 첫 단계.

인증 없이 열려 있다(접수 자체가 로그인 없이 가능한 설계). 돌려주는 것은 학교
이름·교육청 같은 공개 정보뿐이다(schemas/school.py).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import enforce_school_lookup_rate_limit
from app.db.session import get_db
from app.schemas.school import SchoolPublicOut
from app.services.directory import find_school_by_code

router = APIRouter(prefix="/api/schools", tags=["schools"])


@router.get(
    "/by-code/{code}",
    response_model=SchoolPublicOut,
    dependencies=[Depends(enforce_school_lookup_rate_limit)],
)
def get_school_by_code(code: str, db: Session = Depends(get_db)):
    """학교 코드로 학교 찾기. 형식이 틀린 코드도 없는 코드와 똑같이 404."""
    school = find_school_by_code(db, code)
    if school is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "학교를 찾을 수 없습니다. 학교 코드를 확인해 주세요.")
    return school
