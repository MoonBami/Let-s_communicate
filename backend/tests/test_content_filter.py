"""F3 욕설·위협 필터 회귀 테스트.

content_filter.filter_content 가 정상 민원은 통과시키고,
욕설·위협은 차단하는지 자동 검사한다.
필터 패턴을 수정할 때 오차단(정당한 민원을 막는 사고)을 잡기 위한 안전벨트.
"""

from app.services.ai.content_filter import filter_content


# --- 정상 민원: 절대 차단되면 안 됨 (오차단 = 사고) ---

def test_normal_complaint_passes():
    result = filter_content("안녕하세요. 급식 관련해서 문의드립니다.")
    assert result.is_blocked is False


def test_polite_complaint_passes():
    result = filter_content("아이 수행평가 점수 산정 기준이 궁금해서 여쭤봅니다.")
    assert result.is_blocked is False


def test_mild_frustration_passes():
    # 불만은 있지만 욕설·위협이 아니면 통과해야 한다
    result = filter_content("계속 답변이 늦어서 조금 답답합니다. 확인 부탁드려요.")
    assert result.is_blocked is False


# --- 욕설: 차단되어야 함 (severity medium) ---

def test_profanity_is_blocked():
    result = filter_content("씨발 이게 학교냐")
    assert result.is_blocked is True
    assert result.severity == "medium"


# --- 위협: 차단되어야 함 (severity high) ---

def test_threat_is_blocked():
    result = filter_content("가만 안 두겠어")
    assert result.is_blocked is True
    assert result.severity == "high"


# --- 욕설 + 위협 함께: 최고 심각도 (critical) ---

def test_profanity_and_threat_is_critical():
    result = filter_content("이 개새끼 죽여버린다")
    assert result.is_blocked is True
    assert result.severity == "critical"


# --- 증거 수집: 매칭된 표현이 기록되어야 함 ---

def test_matched_terms_are_collected():
    result = filter_content("씨발 진짜")
    assert len(result.matched_terms) > 0
