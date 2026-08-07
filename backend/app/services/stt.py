"""F7: 녹음 → 대화록 변환(STT).

CLOVA Speech(Long Sentence) 를 호출한다. 한국어 정확도와 화자 분리(diarization)
품질 때문에 국내 서비스를 1순위로 둔다.

증빙 자료를 만드는 경로이므로 **설정이 없으면 조용히 넘기지 않고 실패시킨다**
(빈 대화록이 '녹음에 아무 말도 없었다'로 오해될 수 있기 때문).
"""

from dataclasses import dataclass, field

import httpx

from app.core.config import settings


@dataclass
class TranscriptResult:
    full_text: str
    provider: str
    segments: list[dict] = field(default_factory=list)


def transcribe(audio_url: str) -> TranscriptResult:
    if not settings.clova_stt_url or not settings.clova_stt_secret:
        raise RuntimeError("STT 가 설정되지 않았습니다 (CLOVA_STT_URL / CLOVA_STT_SECRET).")

    resp = httpx.post(
        f"{settings.clova_stt_url.rstrip('/')}/recognizer/url",
        headers={
            "X-CLOVASPEECH-API-KEY": settings.clova_stt_secret,
            "Content-Type": "application/json",
        },
        json={
            "url": audio_url,
            "language": "ko-KR",
            "completion": "sync",
            "diarization": {"enable": True},  # 교사/학부모 화자 구분
        },
        timeout=300.0,  # 통화 길이에 비례 — 동기 변환은 오래 걸린다
    )
    resp.raise_for_status()
    data = resp.json()

    return TranscriptResult(
        full_text=data.get("text", ""),
        provider="clova",
        segments=[
            {
                "speaker": seg.get("speaker", {}).get("label"),
                "start": seg.get("start"),
                "end": seg.get("end"),
                "text": seg.get("text"),
            }
            for seg in data.get("segments", [])
        ],
    )
