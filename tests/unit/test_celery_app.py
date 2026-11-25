from app.celery_app import create_celery_app
from app.core.config import Settings
from app.tasks.health import ping


def test_celery_uses_the_configured_broker_and_ignores_results() -> None:
    app = create_celery_app(Settings(_env_file=None))

    assert app.conf.broker_url == "redis://127.0.0.1:6379/1"
    assert app.conf.task_serializer == "json"
    assert app.conf.task_ignore_result is True
    assert app.conf.task_acks_late is True
    assert "dispatch-email-outbox" in app.conf.beat_schedule
    assert "sync-recent-movies" in app.conf.beat_schedule
    assert "sync-recent-series" in app.conf.beat_schedule


def test_ping_task_runs_without_a_broker() -> None:
    result = ping.apply()

    assert result.get() == "pong"
