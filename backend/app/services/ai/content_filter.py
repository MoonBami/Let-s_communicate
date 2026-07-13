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
_THREAT_PATTERNS = [
    r"죽여|죽인다|죽일|쥑",
    r"때려|패\s*버|패죽|두들겨",
    r"없애\s*버|없애줄|없애겠",
    r"가만\s*(안|두지|안둬|안냅)",
    r"두고\s*보|각오해|후회하게|후회할",
    r"찾아\s*가(겠|서|겠어|겠다)",
    r"칼\s*로|칼\s*들고|흉기",
    r"불\s*(지르|질러)",
    r"신상\s*(털|공개)|주소\s*안다",
]

# 욕설·모욕 표현 — 인격 모독. 차단 심각도 medium.
_PROFANITY_PATTERNS = [
    r"씨발|시발|씨빨|ㅅㅂ|시1발|씨1발",
    r"개새끼|개색기|새끼|색기|ㅅㄲ",
    r"병신|븅신|ㅄ|빙신",
    r"지랄|ㅈㄹ|지1랄",
    r"미친놈|미친년|또라이|정신병",
    r"닥쳐|닥치|꺼져|꺼지",
    r"등신|머저리|한심한\s*것",
    r"엿\s*먹|좆|좇|ㅈ같",
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
