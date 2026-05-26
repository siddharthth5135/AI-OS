from celery import Celery

from app.core.config.settings import settings

celery_app = Celery(
    "ai_os",
    broker=settings.celery_broker_url.get_secret_value(),
    backend=settings.celery_result_backend.get_secret_value(),
    include=[
        "app.workers.embedding_worker",
        "app.workers.document_worker",
        "app.workers.cleanup_worker",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    timezone="UTC",
    enable_utc=True,
    task_routes={
        "app.workers.embedding_worker.*": {"queue": "embeddings"},
        "app.workers.document_worker.*": {"queue": "documents"},
        "app.workers.cleanup_worker.*": {"queue": "cleanup"},
    },
    beat_schedule={
        "expire-old-sessions": {
            "task": "app.workers.cleanup_worker.expire_old_sessions",
            "schedule": 3600.0,
        }
    },
)
