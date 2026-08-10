"""F3 욕설·위협 필터 회귀 테스트.

이 필터는 **차단과 증거를 만들어내는** 경로라 회귀가 곧 사고다. 두 방향의
실패가 모두 심각한데, 성격이 다르다.

- **오차단(false positive)**: 정당한 민원이 `filtered_blocked` 로 사라진다.
  교사에게 안 가고, 학부모는 답을 받지 못하며, admin·mdt 만 열람할 수 있다.
  **되돌릴 경로가 없어서 더 위험하다.** 특히 학교폭력을 *신고하는* 민원이
  차단되면 이 서비스의 존재 이유가 무너진다.
- **미차단(false negative)**: 교사가 욕설에 노출된다. F3 의 목적 실패지만,
  F2 위험도 표시와 F8 이관이라는 후속 경로가 남는다.

그래서 통과(오차단 방지) 케이스를 차단 케이스보다 촘촘히 고정한다.

    cd backend && pytest
"""

import pytest

from app.services.ai.content_filter import filter_content

# ---------------------------------------------------------------------------
# 1. 오차단 방지 — 정당한 민원은 절대 막히면 안 된다
# ---------------------------------------------------------------------------

# 학교폭력·부상을 '신고하는' 민원. 가해 표현과 어휘가 겹치지만 차단 대상이 아니다.
REPORTING_COMPLAINTS = [
    "같은 반 친구가 아이를 때려서 팔에 멍이 들었습니다. 상담을 요청드립니다.",
    "아이가 친구들에게 두들겨 맞았다고 합니다. 확인 부탁드립니다.",
    "지속적으로 괴롭힘을 당하고 있어 학폭 신고 절차를 문의드립니다.",
    "아이가 교실에서 밀려 넘어졌다고 하는데 경위를 알고 싶습니다.",
]

# 방문·상담 요청. '찾아가다'가 위협으로 읽히면 안 된다.
VISIT_REQUESTS = [
    "이번 주에 학교에 찾아가서 선생님과 상담하고 싶습니다.",
    "직접 찾아가서 말씀드리는 편이 좋을까요?",
]

# 시설·행정 민원. '꺼지다', '닥치다' 가 일상 어휘로 쓰인 경우.
FACILITY_COMPLAINTS = [
    "교실 난방이 꺼져 있어서 아이가 추웠다고 합니다.",
    "복도 전등이 꺼지지 않아 밤에도 켜져 있습니다.",
    "제출 기한이 닥쳐서 급하게 문의드립니다.",
    "장마철이 닥치기 전에 우산 보관함을 늘려주실 수 있을까요?",
]

# 의료·신체 관련. 민감한 내용을 담은 정당한 민원.
MEDICAL_COMPLAINTS = [
    "아이가 새끼손가락을 다쳐서 깁스를 했습니다. 체육 수업 참여를 문의드립니다.",
    "아이가 정신병원에서 상담 치료를 받고 있어 배려를 부탁드립니다.",
    "아이가 정신과 진료 기록이 있어 담임 선생님께만 알리고 싶습니다.",
]

# 일반적인 정중한 민원
ORDINARY_COMPLAINTS = [
    "급식 식단표를 어디서 확인할 수 있나요?",
    "수행평가 채점 기준을 알고 싶습니다.",
    "현장학습 동의서 제출 기한을 문의드립니다.",
    "담임 선생님과 상담 예약을 하고 싶습니다.",
    "아이가 요즘 학교 생활을 힘들어해서 걱정입니다. 조언을 구합니다.",
]


@pytest.mark.parametrize(
    "text",
    [
        *REPORTING_COMPLAINTS,
        *VISIT_REQUESTS,
        *FACILITY_COMPLAINTS,
        *MEDICAL_COMPLAINTS,
        *ORDINARY_COMPLAINTS,
    ],
)
def test_정당한_민원은_차단되지_않는다(text):
    r = filter_content(text)
    assert not r.is_blocked, f"정당한 민원이 차단됨(matched={r.matched_terms}): {text}"
    assert r.severity == "low"
    assert r.matched_terms == []


# ---------------------------------------------------------------------------
# 2. 차단 — 실제 욕설·위협은 반드시 막는다
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "너 죽여버린다",
        "가만 안 둘 거야",
        # '때려서 다쳤습니다'(신고)와 구분하기 위해 연결형까지 보는 표현들.
        # 패턴을 좁히다가 이쪽이 새어나간 적이 있어 변형을 모두 고정한다.
        "때려죽일 놈",
        "때려버린다",
        "때려 버릴 거야",
        "때려주겠다",
        "패 버리겠다",
        "두들겨 패겠다",
        "두들겨 버린다",
        "학교로 찾아가겠다 각오해라",
        "찾아갈게",
        "찾아갈 거야",
        "칼로 찔러버릴 거야",
        "학교에 불 지르겠다",
        "신상 털어서 인터넷에 공개할 거다",
        "두고 보자",
    ],
)
def test_위협은_차단되고_심각도_high(text):
    r = filter_content(text)
    assert r.is_blocked, f"위협이 통과함: {text}"
    assert r.severity == "high"
    assert r.matched_terms, "증거가 비어 있다"


@pytest.mark.parametrize(
    "text",
    [
        "이 씨발 뭐하는 겁니까",
        "선생이 병신인가",
        "지랄하지 마세요",
        "이 새끼가 우리 애를 무시했다",
        "새끼야",
        # 일상 어휘와 겹쳐 제외 규칙을 붙인 표현들 — 맨 표현은 여전히 차단되어야 한다.
        "닥쳐",
        "닥쳐라",
        "입 닥쳐",
        "꺼져",
        "꺼져라",
        "당장 꺼지세요",
        "정신병자 아닌가",
        "또라이 같은 학교",
        "머저리들",
        "ㅅㅂ 진짜",
    ],
)
def test_욕설은_차단되고_심각도_medium(text):
    r = filter_content(text)
    assert r.is_blocked, f"욕설이 통과함: {text}"
    assert r.severity == "medium"
    assert r.matched_terms


def test_위협과_욕설이_함께면_critical():
    r = filter_content("이 씨발 선생 죽여버린다 가만 안 둬")
    assert r.is_blocked
    assert r.severity == "critical"


@pytest.mark.parametrize("text", ["ㅅㅂ", "시1발", "씨1발", "ㅄ", "ㅈㄹ", "ㅅㄲ"])
def test_초성_숫자_우회도_차단(text):
    assert filter_content(text).is_blocked


# ---------------------------------------------------------------------------
# 3. 증거 수집 — 법적 대응·이의제기에 쓰이므로 형태가 중요하다
# ---------------------------------------------------------------------------


def test_증거는_조각이_아니라_전체_표현():
    r = filter_content("가만 안 둘 거야")
    assert "가만 안" in r.matched_terms, r.matched_terms
    assert "안" not in r.matched_terms, "캡처그룹 조각만 남으면 증거로 못 쓴다"


def test_증거는_중복되지_않는다():
    r = filter_content("씨발 씨발 씨발")
    assert r.matched_terms.count("씨발") == 1


def test_증거에_위협과_욕설이_모두_담긴다():
    r = filter_content("씨발 죽여버린다")
    assert any("죽여" in t for t in r.matched_terms)
    assert any("씨발" in t for t in r.matched_terms)


# ---------------------------------------------------------------------------
# 4. 결정론성 — 이 필터의 존재 이유(같은 입력엔 항상 같은 판정)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    ["씨발 죽여버린다", "급식 식단표를 확인하고 싶습니다", "같은 반 친구가 아이를 때려서 다쳤습니다"],
)
def test_같은_입력은_항상_같은_결과(text):
    a, b = filter_content(text), filter_content(text)
    assert (a.is_blocked, a.severity, a.matched_terms) == (b.is_blocked, b.severity, b.matched_terms)


def test_모델명이_규칙기반으로_고정():
    assert filter_content("아무 내용").model_name == "rule-filter-v1"


# ---------------------------------------------------------------------------
# 5. 경계 입력
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text", ["", " ", "\n", "...", "1234"])
def test_빈_입력이나_기호는_통과(text):
    r = filter_content(text)
    assert not r.is_blocked
    assert r.severity == "low"
