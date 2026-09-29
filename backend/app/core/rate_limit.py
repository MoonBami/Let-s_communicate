"""유량 제한 — 공개 접수 엔드포인트를 대량 제출로부터 보호한다.

`POST /api/complaints` 는 인증이 없다(학부모에게 로그인을 강제하지 않는 설계).
따라서 스크립트로 초당 수백 건을 넣으면 DB 가 차고 교사 민원함이 마비된다.

## 이 도메인에서의 판단 두 가지

**1. Redis 가 죽으면 통과시킨다(fail-open).**
막는 쪽(fail-closed)을 택하면 Redis 장애가 곧 '모든 민원 접수 중단'이 된다.
학교폭력 신고까지 못 들어온다. 이 프로젝트에서 가장 비싼 실패는 정당한 민원이
사라지는 것이므로(F3 오차단 수정·자동응대 게이트와 같은 기준), 유량 제한이
꺼지는 쪽을 택하고 대신 **경고를 남긴다.**

**2. 익명 접수의 분당 한도는 넉넉해야 한다.**
학부모들이 같은 학교 와이파이나 통신사 NAT 뒤에 있으면 IP 가 겹친다. 학교에서
사건이 터지면 여러 학부모가 동시에 민원을 넣는데, 이때 한도가 빡빡하면 **정당한
민원이 서로를 막는다.** 그래서 사람이 절대 넘길 수 없는 수준(분당 몇 건)으로만
잡아 스크립트를 걸러내고, 시간당 한도는 NAT 를 고려해 크게 둔다.

로그인한 학부모는 IP 가 아니라 **사용자 id** 로 세므로 NAT 문제가 없다.

## 알고리즘

고정 윈도(fixed window) 카운터다. 윈도 경계에서 순간적으로 한도의 2배까지
허용될 수 있으나, 목적이 '스크립트성 대량 제출 차단'이므로 충분하다.
정교한 슬라이딩 윈도는 복잡도만 늘린다.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from urllib.parse import urlsplit

from app.core.config import settings

logger = logging.getLogger(__name__)

_KEY_PREFIX = "ratelimit"


@dataclass(frozen=True)
class RateRule:
    """`window_seconds` 안에 `limit` 회까지 허용."""

    limit: int
    window_seconds: int

    @property
    def name(self) -> str:
        return f"{self.limit}/{self.window_seconds}s"


@dataclass
class RateVerdict:
    allowed: bool
    retry_after: int = 0
    rule: str = ""


class _MemoryCounter:
    """프로세스 내 카운터. Redis 가 없을 때 쓰는 대체 경로.

    워커·인스턴스마다 따로 세므로 정확하지 않다. 그래도 단일 프로세스로 돌리는
    개발·데모 환경에서는 실질적인 보호가 되고, 무엇보다 테스트가 Redis 를
    요구하지 않게 된다.
    """

    def __init__(self) -> None:
        self._hits: dict[str, tuple[int, float]] = {}
        self._lock = threading.Lock()

    def hit(self, key: str, rule: RateRule, now: float) -> tuple[int, int]:
        """returns (현재 횟수, 윈도 잔여 초)

        규칙(윈도 길이)별로 카운터를 나눈다. 나누지 않으면 분당·시간당 규칙이
        같은 카운터를 공유해 서로의 횟수를 부풀린다 — Redis 쪽은 키에 윈도를
        넣어 이미 나누고 있었으므로, 두 백엔드의 동작이 갈리는 버그였다.
        """
        slot = f"{key}:{rule.window_seconds}"
        with self._lock:
            count, window_start = self._hits.get(slot, (0, now))
            if now - window_start >= rule.window_seconds:
                count, window_start = 0, now
            count += 1
            self._hits[slot] = (count, window_start)
            remaining = int(rule.window_seconds - (now - window_start)) + 1
            return count, remaining

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


class _RedisCounter:
    """Redis 고정 윈도 카운터. 여러 워커·인스턴스가 같은 카운터를 공유한다."""

    def __init__(self, client) -> None:
        self._client = client

    def hit(self, key: str, rule: RateRule, now: float) -> tuple[int, int]:
        window = int(now // rule.window_seconds)
        redis_key = f"{_KEY_PREFIX}:{key}:{rule.window_seconds}:{window}"
        pipe = self._client.pipeline()
        pipe.incr(redis_key)
        pipe.expire(redis_key, rule.window_seconds)
        count, _ = pipe.execute()
        remaining = rule.window_seconds - int(now % rule.window_seconds)
        return int(count), max(1, remaining)


def _redact(url: str) -> str:
    """로그용 Redis 주소 — 비밀번호를 뺀 `scheme://host:port` 만 남긴다.

    Upstash 같은 관리형 Redis 는 주소에 비밀번호가 들어 있어서, 통째로 찍으면
    배포 로그(Vercel 등)에 자격 증명이 그대로 남는다.
    """
    try:
        parts = urlsplit(url)
        host = parts.hostname or "?"
        port = f":{parts.port}" if parts.port else ""
        return f"{parts.scheme}://{host}{port}"
    except ValueError:
        return "<redis_url 파싱 실패>"


_memory = _MemoryCounter()
_redis_counter: _RedisCounter | None = None
_redis_checked = False


def _counter():
    """Redis 를 우선 쓰고, 못 붙으면 프로세스 내 카운터로 떨어진다."""
    global _redis_counter, _redis_checked

    if not _redis_checked:
        _redis_checked = True
        try:
            import redis

            client = redis.Redis.from_url(settings.redis_url, socket_timeout=0.3)
            client.ping()
            _redis_counter = _RedisCounter(client)
            logger.info("rate_limit | Redis 카운터 사용: %s", _redact(settings.redis_url))
        except Exception as exc:
            logger.warning(
                "rate_limit | Redis 에 붙지 못해 프로세스 내 카운터로 동작한다 "
                "(워커·인스턴스별로 따로 세므로 정확하지 않음): %s",
                exc,
            )

    return _redis_counter or _memory


def check(key: str, rules: tuple[RateRule, ...]) -> RateVerdict:
    """모든 규칙을 검사한다. 하나라도 초과하면 거부.

    저장소 오류는 통과로 처리한다(fail-open) — 위 모듈 설명 참고.
    """
    now = time.time()
    counter = _counter()

    for rule in rules:
        try:
            count, remaining = counter.hit(key, rule, now)
        except Exception:
            logger.exception("rate_limit | 카운터 오류 → 통과시킨다(fail-open) key=%s", key)
            return RateVerdict(allowed=True)

        if count > rule.limit:
            return RateVerdict(allowed=False, retry_after=remaining, rule=rule.name)

    return RateVerdict(allowed=True)


def intake_rules() -> tuple[RateRule, ...]:
    """민원 접수 한도. 설정으로 조정 가능(운영 중 튜닝 필요할 수 있음)."""
    return (
        RateRule(settings.rate_limit_intake_per_minute, 60),
        RateRule(settings.rate_limit_intake_per_hour, 3600),
    )


def school_lookup_rules() -> tuple[RateRule, ...]:
    """학교 코드 조회 한도(`GET /api/schools/by-code/{code}`)."""
    return (RateRule(settings.rate_limit_school_lookup_per_minute, 60),)


def guest_lookup_rules() -> tuple[RateRule, ...]:
    """비회원 민원 조회 한도(`POST /api/complaints/lookup`) — IP 기준."""
    return (RateRule(settings.rate_limit_guest_lookup_per_minute, 60),)


def reset_for_tests() -> None:
    """테스트 격리용 — 프로세스 내 카운터를 비운다."""
    _memory.reset()
