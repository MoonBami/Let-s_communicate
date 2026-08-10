"""F3: 욕설·위협 필터.

설계 원칙 — 이 필터는 '증거'와 '차단'을 만들어내므로 **결정론적**이어야 한다.
같은 입력엔 항상 같은 판정이 나와야 하고(법적·이의제기 대응), LLM의 확률적
판단에만 맡기지 않는다. 그래서 정규식/키워드 규칙을 1차 기준으로 삼고,
원문(raw_evidence)은 마스킹 없이 그대로 증거로 보관한다(접근 통제·암호화는 저장 계층 책임).

차단(blocked)되면 교사에게 노출되지 않고 status=filtered_blocked 로 증거만 남는다.
"""

import re
from dataclasses import dataclass, field

# 위협성 표현 — 신체적 위해·협박. 차단 심각도 high.
#
# ⚠️ 패턴을 넓히기 전에 tests/test_content_filter.py 를 먼저 볼 것.
# 폭력을 *신고하는* 민원은 가해 표현과 어휘가 겹친다("친구가 아이를 때려서 다쳤습니다").
# 어휘 하나만 보고 차단하면 학교폭력 신고가 교사에게 가지 못하고 사라진다 —
# 이 서비스가 막으려는 문제를 필터가 만들어내는 셈이다. 그래서 위협 표현은
# **가해 의도가 드러나는 연결형까지 함께** 요구한다(때려'죽', 두들겨'패').
_THREAT_PATTERNS = [
    r"죽여|죽인다|죽일|쥑",
    # '때려서 다쳤습니다'(신고)는 통과, '때려죽/때려버/때려주겠'(가해 의도)은 차단.
    r"때려\s*(죽|버|팰|주겠|줄)|패\s*버|패죽|두들겨\s*(패|버|줄|주겠)",
    r"없애\s*버|없애줄|없애겠",
    r"가만\s*(안|두지|안둬|안냅)",
    r"두고\s*(보자|봐|볼\s*테)|각오해|후회하게|후회할",
    # '찾아가서'는 방문 상담 요청("학교에 찾아가서 상담하고 싶습니다")이라 제외.
    r"찾아\s*가겠|찾아\s*갈(\s*(테|거)|게|께)",
    r"칼\s*로|칼\s*들고|흉기",
    r"불\s*(지르|질러)",
    r"신상\s*(털|공개)|주소\s*안다",
]

# 욕설·모욕 표현 — 인격 모독. 차단 심각도 medium.
#
# 일상 어휘와 겹치는 표현은 부정 전방·후방탐색으로 정당한 용례를 제외한다.
# (앞에 '이/가'가 붙은 '꺼져·닥쳐'는 사물 주어 = 시설·기한 민원이다)
_PROFANITY_PATTERNS = [
    r"씨발|시발|씨빨|ㅅㅂ|시1발|씨1발",
    # '새끼손가락' 제외
    r"개새끼|개색기|새끼(?!손)|색기|ㅅㄲ",
    r"병신|븅신|ㅄ|빙신",
    r"지랄|ㅈㄹ|지1랄",
    # '정신병원·정신병력·정신병동'(진료 사실 언급) 제외
    r"미친놈|미친년|또라이|정신병(?![원력동])",
    # '기한이 닥쳐서', '난방이 꺼져' 제외
    r"(?<![이가]\s)(?<![이가])닥[쳐치]|(?<![이가]\s)(?<![이가])꺼[져지]",
    r"등신|머저리|한심한\s*것",
    # '좇다'(따르다)는 정상 어휘라 제외
    r"엿\s*먹|좆|ㅈ같",
]

_THREAT_RE = [re.compile(p) for p in _THREAT_PATTERNS]
_PROFANITY_RE = [re.compile(p) for p in _PROFANITY_PATTERNS]


@dataclass
class FilterResult:
    is_blocked: bool
    severity: str  # risk_level: low/medium/high/critical
    matched_terms: list[str] = field(default_factory=list)
    model_name: str = "rule-filter-v1"


def filter_content(text: str) -> FilterResult:
    """욕설·위협을 탐지해 차단 여부와 증거(매칭 표현)를 돌려준다.

    - 위협 표현이 있으면 severity=high, 차단.
    - 욕설만 있으면 severity=medium, 차단.
    - 위협·욕설이 함께 있으면 severity=critical.
    - 아무것도 없으면 통과(is_blocked=False).
    """
    threats = _collect(text, _THREAT_RE)
    profanity = _collect(text, _PROFANITY_RE)

    matched = threats + profanity
    if not matched:
        return FilterResult(is_blocked=False, severity="low")

    if threats and profanity:
        severity = "critical"
    elif threats:
        severity = "high"
    else:
        severity = "medium"

    return FilterResult(is_blocked=True, severity=severity, matched_terms=matched)


def _collect(text: str, patterns: list[re.Pattern[str]]) -> list[str]:
    """중복 없이 매칭된 '전체' 표현을 수집(증거용).

    finditer + group(0) 으로 캡처그룹이 아닌 매칭 문자열 전체를 남긴다
    (예: '가만 안', '찾아가서', '죽여' — 조각 '안'/'서' 가 아니라).
    """
    found: list[str] = []
    for pat in patterns:
        for m in pat.finditer(text):
            token = m.group(0).strip()
            if token and token not in found:
                found.append(token)
    return found
