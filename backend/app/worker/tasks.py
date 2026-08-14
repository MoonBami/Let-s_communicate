"""비동기 태스크 — 요청 경로에 두면 응답이 느려지는 작업들.

- F5 사례 임베딩 인덱싱 (단건 / 누락분 배치)
- F7 녹음 STT 변환

재시도 정책: DB 순간 끊김(OperationalError)이나 STT 외부 API의 일시적
네트워크 오류(httpx.TransportError)만 재시도 대상으로 삼는다. ValueError
같은 "데이터 자체가 잘못된" 오류는 재시도해도 결과가 똑같으므로 재시도하지
않고 바로 실패시킨다.
"""

import httpx
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.db.session import SessionLocal
from app.models.case import CaseEmbedding, ComplaintCase
from app.models.recording import Recording, Transcript
from app.services.ai import index_case
from app.services.stt import transcribe
from app.worker.celery_app import celery_app

# DB 순간 끊김 재시도 공통 옵션. 지수 백오프(2s, 4s, 8s ...)로 최대 3회.
_DB_RETRY = dict(
    autoretry_for=(OperationalError,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=3,
)


@celery_app.task(name="app.worker.tasks.index_case_embedding", **_DB_RETRY)
def index_case_embedding(case_id: str) -> str:
    """단건 사례 임베딩 생성·갱신. 사용한 임베딩 모델명을 반환."""
    with SessionLocal() as db:
        case = db.get(ComplaintCase, case_id)
        if case is None:
            raise ValueError(f"사례를 찾을 수 없습니다: {case_id}")
        model_name = index_case(db, case)
        db.commit()
        return model_name


@celery_app.task(name="app.worker.tasks.reindex_missing_case_embeddings", **_DB_RETRY)
def reindex_missing_case_embeddings(limit: int = 200) -> int:
    """임베딩이 없는 사례를 채운다(beat 주기 실행). 처리 건수를 반환."""
    with SessionLocal() as db:
        cases = db.execute(
            select(ComplaintCase)
            .outerjoin(CaseEmbedding, CaseEmbedding.case_id == ComplaintCase.id)
            .where(CaseEmbedding.case_id.is_(None))
            .limit(limit)
        ).scalars().all()

        for case in cases:
            index_case(db, case)
        db.commit()
        return len(cases)


@celery_app.task(
    name="app.worker.tasks.transcribe_recording",
    # STT 는 DB 끊김 + CLOVA 쪽 일시적 네트워크 오류(타임아웃·연결 실패)까지
    # 재시도 대상. 4xx/5xx 응답(HTTPStatusError)은 재시도해도 똑같이 실패할
    # 가능성이 높아 제외 — 재시도는 "다시 하면 될 수도 있는" 오류에만 건다.
    autoretry_for=(OperationalError, httpx.TransportError),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=3,
)
def transcribe_recording(recording_id: str) -> str:
    """녹음을 대화록으로 변환해 저장. 생성된 transcript id 를 반환.

    녹음 고지·동의가 기록되지 않은 건은 변환하지 않는다(통신비밀보호법).
    """
    with SessionLocal() as db:
        recording = db.get(Recording, recording_id)
        if recording is None:
            raise ValueError(f"녹음을 찾을 수 없습니다: {recording_id}")
        if not recording.consent_given:
            raise ValueError("녹음 고지·동의가 기록되지 않아 변환할 수 없습니다.")

        result = transcribe(recording.storage_url)
        transcript = Transcript(
            recording_id=recording.id,
            full_text=result.full_text,
            segments=result.segments,
            stt_provider=result.provider,
        )
        db.add(transcript)
        db.commit()
        return str(transcript.id)
