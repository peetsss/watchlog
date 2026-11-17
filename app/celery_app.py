from celery import Celery
from celery.signals import worker_process_init, worker_process_shutdown

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.core.observability import init_sentry
from app.workers.runtime import dispose_worker_runtime, init_worker_runtime

TASK_MODULES = ("app.tasks.health",)


def create_celery_app(settings: Settings | None = None) -> Celery:
    resolved_settings = settings or get_settings()
    celery_app = Celery(
        "watchlog",
        broker=resolved_settings.celery_broker_url,
        include=list(TASK_MODULES),
    )
    celery_app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_backend=None,
        task_ignore_result=True,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        worker_max_tasks_per_child=100,
        broker_connection_retry_on_startup=True,
        timezone="UTC",
        enable_utc=True,
    )
    return celery_app


celery_app = create_celery_app()


@worker_process_init.connect
def initialize_worker_process(**_: object) -> None:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    init_sentry(settings)
    init_worker_runtime(settings)


@worker_process_shutdown.connect
def shutdown_worker_process(**_: object) -> None:
    dispose_worker_runtime()
