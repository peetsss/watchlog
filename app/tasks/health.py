from app.celery_app import celery_app


@celery_app.task(name="watchlog.ping")
def ping() -> str:
    return "pong"
