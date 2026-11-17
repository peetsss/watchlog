import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.fastapi import FastApiIntegration

from app import __version__
from app.core.config import Settings


def init_sentry(settings: Settings) -> None:
    dsn = settings.sentry_dsn.get_secret_value()
    if not dsn:
        return
    sentry_sdk.init(
        dsn=dsn,
        environment=settings.env,
        release=__version__,
        send_default_pii=False,
        traces_sample_rate=0.0,
        integrations=[FastApiIntegration(), CeleryIntegration()],
    )
