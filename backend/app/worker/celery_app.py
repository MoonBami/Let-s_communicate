"""Celery 앱 — 요청 경로에서 떼어내야 하는 무거운 작업 전용.

브로커·결과 백엔드는 모두 Redis(`REDIS_URL`).

실행:
    celery -A app.worker.celery_app:celery_app worker --loglevel=info
    celery -A app.worker.celery_app:celery_app beat   --loglevel=info   # 주기 작업
"""

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "sotong",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Seoul",
    enable_utc=True,
    task_track_started=True,
    # STT 는 통화 길이에 비례해 오래 걸리므로 워커 기본 타임아웃을 넉넉히.
    task_soft_time_limit=600,
    task_time_limit=900,
    # Celery 6.0 이후 브로커 연결 재시도 기본 동작이 바뀌는데, 기동 시
    # Redis 가 아직 안 떠 있어도(docker-compose 기동 순서) 계속 재시도하게
    # 명시적으로 켜둔다. (안 켜두면 워커가 그냥 죽어버릴 수 있음)
    broker_connection_retry_on_startup=True,
    # 작업 도중 워커가 죽어도(컨테이너 재시작·OOM 등) 메시지를 유실하지 않고
    # 다른 워커가 이어받게 한다. 대신 태스크가 멱등적이어야 함 —
    # index_case_embedding 은 upsert 성격이라 중복 실행돼도 안전.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # 워커 하나가 한 번에 여러 작업을 미리 채가지 않도록(공평 분배).
    # 특히 STT 처럼 오래 걸리는 작업이 짧은 작업을 오래 막지 않게.
    worker_prefetch_multiplier=1,
    beat_schedule={
        # 임베딩이 없는 사례를 매일 새벽에 채운다(등록 시 실패했거나 임베딩
        # 모델을 바꾼 경우 대비).
        "reindex-missing-case-embeddings": {
            "task": "app.worker.tasks.reindex_missing_case_embeddings",
            "schedule": crontab(hour=4, minute=0),
        },
    },
)
