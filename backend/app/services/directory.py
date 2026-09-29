"""학교·학생 찾기 — 민원 접수에서 '어느 학교의 어느 학생 건인가'를 정한다.

## 학교: 코드로 공개 조회

학교 코드는 학부모가 가정통신문 등으로 받아 입력하는 **공개 식별자**다. 학교 이름·
교육청은 원래 공개 정보이므로 코드로 조회하는 API 를 인증 없이 열어 둔다
(`GET /api/schools/by-code/{code}`).

## 학생: 공개 검색은 두지 않는다

학생은 미성년자다. "이 학교 3학년 2반에 김OO 이 있는가"를 아무나 물어볼 수 있게
하면, 로그인 없이 특정 아이의 재학 여부·학년·반을 캐낼 수 있다. 그래서 학생 검색
엔드포인트는 만들지 않고, **접수 요청 안에서 서버가 조용히 찾는다.** 찾았는지
여부는 접수 응답에도 드러내지 않는다(routes/complaints.py).

찾는 규칙은 보수적이다.
- 반드시 **같은 학교 안에서만** 찾는다.
- 이름·학년·반이 모두 맞는 학생이 **정확히 1명**일 때만 연결한다.
  동명이인이 있거나 못 찾으면 연결하지 않는다(None). 잘못 연결하면 민원이
  **엉뚱한 아이의 담임에게** 간다 — 민원 내용이 제3자 교사에게 노출되는 셈이라,
  연결하지 않고 관리자가 수동 배정하게 두는 편이 낫다.
- 못 찾았다고 접수를 거부하지 않는다. 학생 정보가 틀려도 민원 자체는 들어와야 한다.
- 학생을 연결하지 못해도 **담임 배정은 학부모가 적은 학년·반으로 한다**
  (routes/complaints.py → routing.route_by_class). 학생 명단이 없는 학교도 교사에게
  반만 배정하면 자동 배정이 돈다. 동명이인이어도 둘 다 같은 반이라 담임은 같다.

`student_id` 를 직접 주는 경로(기존 클라이언트·로그인 학부모 화면)는 유지하되,
**다른 학교 학생이면 없는 학생으로 취급한다.** 전에는 검사하지 않아 A 학교로
접수한 민원이 B 학교 학생의 담임에게 라우팅될 수 있었다.
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import School, Student

logger = logging.getLogger(__name__)

# 학교 코드 허용 형식. 교육청 행정표준코드(숫자 7자리)와 데모 코드(DEMO001)를
# 모두 받되, 경로 파라미터로 이상한 문자열이 DB 까지 가지 않게 막는다.
SCHOOL_CODE_PATTERN = r"^[A-Za-z0-9-]{3,20}$"
_SCHOOL_CODE_RE = re.compile(SCHOOL_CODE_PATTERN)

_WS_RE = re.compile(r"\s+")


def normalize_school_code(code: str) -> str | None:
    """앞뒤 공백 제거 + 대문자. 형식에 맞지 않으면 None."""
    cleaned = (code or "").strip().upper()
    if not _SCHOOL_CODE_RE.fullmatch(cleaned):
        return None
    return cleaned


def find_school_by_code(db: Session, code: str) -> School | None:
    normalized = normalize_school_code(code)
    if normalized is None:
        return None
    return db.execute(select(School).where(School.code == normalized)).scalar_one_or_none()


def normalize_student_name(name: str) -> str:
    """앞뒤 공백 제거, 내부 공백은 하나로. ('김  학생 ' → '김 학생')"""
    return _WS_RE.sub(" ", (name or "").strip())


def normalize_class_name(class_name: str) -> str:
    """학부모 입력('2반', ' 2 ')을 저장 형식('2')에 맞춘다.

    시드·학적 데이터는 반을 숫자 문자열로 저장한다. 학부모는 대개 '2반'이라고
    쓰므로 끝의 '반'만 떼어 낸다. '햇살반' 같은 이름형 반은 '햇살'이 되는데,
    저장 쪽도 같은 규칙으로 맞추지 않으면 못 찾는다 — 그 경우 연결되지 않을 뿐
    접수는 된다.
    """
    cleaned = _WS_RE.sub("", (class_name or "").strip())
    if cleaned.endswith("반") and len(cleaned) > 1:
        cleaned = cleaned[:-1]
    return cleaned


@dataclass(frozen=True)
class StudentQuery:
    name: str
    grade: int
    class_name: str


class StudentNotInSchool(Exception):
    """직접 준 student_id 가 없거나 다른 학교 학생이다."""


def check_student_in_school(db: Session, school_id: uuid.UUID, student_id: uuid.UUID) -> uuid.UUID:
    """직접 지정한 학생이 이 학교 학생인지 확인.

    없는 학생과 다른 학교 학생을 **구분하지 않는다** — 구분해 알려주면
    임의의 UUID 가 어느 학교 학생인지 떠볼 수 있다.
    """
    student = db.get(Student, student_id)
    if student is None or student.school_id != school_id:
        raise StudentNotInSchool
    return student.id


def find_student_in_school(db: Session, school_id: uuid.UUID, query: StudentQuery) -> uuid.UUID | None:
    """이름·학년·반이 모두 맞는 학생이 정확히 1명일 때만 그 id, 아니면 None."""
    name = normalize_student_name(query.name)
    class_name = normalize_class_name(query.class_name)
    if not name or not class_name:
        return None

    # 2건까지만 가져오면 '정확히 1명인가'를 판정하기에 충분하다.
    rows = db.execute(
        select(Student.id)
        .where(
            Student.school_id == school_id,
            Student.grade == query.grade,
            Student.class_name == class_name,
            Student.name == name,
        )
        .limit(2)
    ).scalars().all()

    if len(rows) == 1:
        return rows[0]

    # 이름은 남기지 않는다(미성년자 개인정보). 매칭 품질을 볼 수 있을 만큼만.
    logger.info(
        "directory | 학생 자동 연결 안 함 school=%s grade=%s class=%s matches=%s",
        school_id, query.grade, class_name, "0" if not rows else "2+",
    )
    return None
