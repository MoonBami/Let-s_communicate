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
    beat_schedule={
        # 임베딩이 없는 사례를 매일 새벽에 채운다(등록 시 실패했거나 임베딩
        # 모델을 바꾼 경우 대비).
        "reindex-missing-case-embeddings": {
            "task": "app.worker.tasks.reindex_missing_case_embeddings",
            "schedule": crontab(hour=4, minute=0),
        },
    },
)
