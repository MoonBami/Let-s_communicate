"""비회원 민원 조회 — 접수번호 + 숫자 4자리 비밀번호.

학부모 대부분은 로그인 없이 접수한다. 접수할 때 서버가 접수번호를, 학부모가 숫자
4자리 비밀번호를 정하고, 둘을 함께 넣어야 민원과 답변을 볼 수 있다(택배 조회 방식).

## 보안의 무게는 접수번호가 진다

비밀번호가 4자리(1만 가지)라 비밀번호만으로는 막을 수 없다. 그래서
- 접수번호를 **추측할 수 없게** 만든다. 헷갈리는 글자(0/O, 1/I/L)를 뺀 32자에서
  8자를 무작위로 뽑는다 → 약 1조 가지. 순번(예: 2026-0001)이면 남의 번호를 짐작할 수 있다.
- 한 접수번호에 비밀번호를 여러 번 틀리면 **잠시 잠근다.** 없으면 접수번호를 본
  사람(어깨너머, 공유된 캡처)이 1만 번을 몇 초 만에 대입해 연다. 잠금 동안에는
  맞는 비밀번호도 거절한다 — 그래야 대입이 실제로 막힌다.
  `GUEST_LOOKUP_MAX_FAILURES=0` 이면 잠금을 끈다.

틀린 접수번호와 틀린 비밀번호는 **같은 응답(404)** 이다. 구분해 주면 "이 접수번호는
존재한다"는 사실부터 새어 나간다.

잃어버린 접수번호·비밀번호는 되찾을 수 없다(연락처를 받지 않는 설계 결정).
"""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.models.complaint import Complaint

# 0/O, 1/I/L 처럼 손으로 옮겨 적다 헷갈리는 글자는 뺀다.
_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
_CODE_LEN = 8
PIN_PATTERN = r"^\d{4}$"
_PIN_RE = re.compile(PIN_PATTERN)


def new_receipt_code(db: Session) -> str:
    """겹치지 않는 접수번호. 저장 형식은 하이픈 없는 대문자 8자."""
    for _ in range(10):
        code = "".join(secrets.choice(_ALPHABET) for _ in range(_CODE_LEN))
        exists = db.execute(select(Complaint.id).where(Complaint.receipt_code == code)).first()
        if exists is None:
            return code
    raise RuntimeError("접수번호 생성 실패")  # 1조 분의 1 이 열 번 연속 — 사실상 불가능


def display_code(code: str) -> str:
    """사람이 읽기 좋게 'ABCD-2345'."""
    return f"{code[:4]}-{code[4:]}"


def normalize_code(raw: str) -> str:
    """'abcd-2345', ' ABCD 2345 ' → 'ABCD2345'."""
    return re.sub(r"[\s-]", "", (raw or "")).upper()


def hash_pin(pin: str) -> str:
    if not _PIN_RE.fullmatch(pin or ""):
        raise ValueError("비밀번호는 숫자 4자리여야 합니다.")
    return hash_password(pin)


@dataclass
class LookupResult:
    complaint: Complaint | None = None
    locked_seconds: int = 0  # >0 이면 잠금 중


def lookup(db: Session, raw_code: str, pin: str) -> LookupResult:
    """접수번호·비밀번호가 맞으면 민원. 틀리면 실패를 세고, 한도를 넘으면 잠근다."""
    code = normalize_code(raw_code)
    complaint = None
    if len(code) == _CODE_LEN:
        complaint = db.execute(
            select(Complaint).where(Complaint.receipt_code == code)
        ).scalar_one_or_none()
    if complaint is None or complaint.lookup_pin_hash is None:
        return LookupResult()

    now = datetime.now(timezone.utc)
    if complaint.lookup_locked_until is not None and complaint.lookup_locked_until > now:
        return LookupResult(locked_seconds=int((complaint.lookup_locked_until - now).total_seconds()) + 1)

    if _PIN_RE.fullmatch(pin or "") and verify_password(pin, complaint.lookup_pin_hash):
        if complaint.lookup_fail_count:
            complaint.lookup_fail_count = 0
            db.commit()
        return LookupResult(complaint=complaint)

    limit = settings.guest_lookup_max_failures
    if limit > 0:
        complaint.lookup_fail_count = (complaint.lookup_fail_count or 0) + 1
        if complaint.lookup_fail_count >= limit:
            complaint.lookup_fail_count = 0
            complaint.lookup_locked_until = now + timedelta(minutes=settings.guest_lookup_lock_minutes)
        db.commit()
    return LookupResult()
