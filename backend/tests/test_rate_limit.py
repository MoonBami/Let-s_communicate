"""유량 제한 정책 테스트 (DB·Redis 없이 프로세스 내 카운터로).

접수 엔드포인트는 인증이 없어서 유량 제한이 유일한 방어선이다. 동시에 이 도메인에선
**정당한 민원을 막는 것이 더 비싼 실패**이므로, 다음 두 성질을 특히 고정한다.

1. 저장소(Redis)가 죽으면 **통과**시킨다 — 막으면 Redis 장애가 곧 접수 중단이다
2. 키가 다르면 서로 영향이 없다 — 한 사람의 과다 제출이 다른 학부모를 막지 않는다
"""

import pytest

from app.core import rate_limit
from app.core.rate_limit import RateRule, check, intake_rules, reset_for_tests


@pytest.fixture(autouse=True)
def _clean():
    reset_for_tests()
    yield
    reset_for_tests()


@pytest.fixture()
def memory_only(monkeypatch):
    """Redis 탐색을 건너뛰고 프로세스 내 카운터를 쓰게 한다."""
    monkeypatch.setattr(rate_limit, "_redis_counter", None)
    monkeypatch.setattr(rate_limit, "_redis_checked", True)


ONE_PER_MIN = (RateRule(1, 60),)
THREE_PER_MIN = (RateRule(3, 60),)


# --- 기본 동작 --------------------------------------------------------------


def test_한도_안에서는_통과(memory_only):
    for _ in range(3):
        assert check("k", THREE_PER_MIN).allowed


def test_한도를_넘으면_거부(memory_only):
    for _ in range(3):
        check("k", THREE_PER_MIN)
    verdict = check("k", THREE_PER_MIN)
    assert not verdict.allowed
    assert verdict.rule == "3/60s"


def test_거부시_재시도_시간을_알려준다(memory_only):
    check("k", ONE_PER_MIN)
    verdict = check("k", ONE_PER_MIN)
    assert not verdict.allowed
    assert 0 < verdict.retry_after <= 61


# --- 키 격리 (같은 NAT 뒤 학부모들이 서로를 막지 않아야 한다) ----------------


def test_키가_다르면_서로_영향이_없다(memory_only):
    check("ip:1.1.1.1", ONE_PER_MIN)
    assert not check("ip:1.1.1.1", ONE_PER_MIN).allowed
    assert check("ip:2.2.2.2", ONE_PER_MIN).allowed, "한 사람 때문에 다른 사람이 막히면 안 된다"


def test_로그인_사용자와_익명은_다른_키(memory_only):
    check("user:abc", ONE_PER_MIN)
    assert check("ip:1.1.1.1", ONE_PER_MIN).allowed


# --- 여러 규칙 -------------------------------------------------------------


def test_규칙_중_하나만_넘어도_거부(memory_only):
    rules = (RateRule(10, 60), RateRule(2, 3600))
    assert check("k", rules).allowed
    assert check("k", rules).allowed
    verdict = check("k", rules)
    assert not verdict.allowed
    assert verdict.rule == "2/3600s", "초과한 규칙을 알려줘야 튜닝할 수 있다"


def test_규칙별로_카운터가_분리된다(memory_only):
    """분당·시간당 규칙이 카운터를 공유하면 서로의 횟수를 부풀려 조기에 막힌다.

    실제로 그런 버그가 있었다 — Redis 백엔드는 키에 윈도를 넣어 나누는데
    프로세스 내 카운터는 나누지 않아 두 경로의 동작이 달랐다.
    """
    rules = (RateRule(5, 60), RateRule(5, 3600))
    # 규칙이 둘이어도 요청 5번은 통과해야 한다(각 카운터가 5까지).
    for i in range(5):
        assert check("k", rules).allowed, f"{i + 1}번째 요청이 막혔다"
    assert not check("k", rules).allowed


def test_윈도가_지나면_다시_통과(memory_only, monkeypatch):
    import time as _time

    base = 1_000_000.0
    monkeypatch.setattr(_time, "time", lambda: base)
    monkeypatch.setattr(rate_limit.time, "time", lambda: base)
    check("k", ONE_PER_MIN)
    assert not check("k", ONE_PER_MIN).allowed

    monkeypatch.setattr(rate_limit.time, "time", lambda: base + 61)
    assert check("k", ONE_PER_MIN).allowed


# --- fail-open (이 도메인에서 가장 중요한 성질) -----------------------------


def test_카운터가_터지면_통과시킨다(memory_only, monkeypatch):
    """Redis 장애가 '모든 민원 접수 중단'이 되면 안 된다.

    학교폭력 신고까지 막히는 것보다, 유량 제한이 잠시 꺼지는 편이 낫다.
    """

    class _Broken:
        def hit(self, *_args, **_kwargs):
            raise RuntimeError("redis down")

    monkeypatch.setattr(rate_limit, "_counter", lambda: _Broken())
    assert check("k", ONE_PER_MIN).allowed


# --- 기본 설정값 -----------------------------------------------------------


def test_기본_한도가_사람의_사용을_막지_않는_수준():
    minute, hour = intake_rules()
    assert minute.window_seconds == 60
    assert hour.window_seconds == 3600
    # 사람이 1분에 5건을 손으로 쓰는 것은 사실상 불가능하고,
    # 시간당 한도는 같은 NAT 뒤 여러 학부모를 고려해 넉넉해야 한다.
    assert 3 <= minute.limit <= 10
    assert hour.limit >= 50, "학교에서 사건이 터지면 여러 학부모가 동시에 접수한다"
