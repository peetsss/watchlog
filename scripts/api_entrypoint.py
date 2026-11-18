#!/usr/bin/env python
import os
import socket
import time
from urllib.parse import urlparse

from sqlalchemy.engine import make_url

from app.core.config import get_settings

STARTUP_TIMEOUT_SECONDS = 60
CONNECT_TIMEOUT_SECONDS = 2
RETRY_INTERVAL_SECONDS = 0.5


def wait_for_tcp(host: str, port: int) -> None:
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=CONNECT_TIMEOUT_SECONDS):
                return
        except OSError:
            time.sleep(RETRY_INTERVAL_SECONDS)
    raise SystemExit(f"Timed out waiting for {host}:{port}")


def main() -> None:
    settings = get_settings()

    database = make_url(settings.sqlalchemy_url)
    wait_for_tcp(database.host or "127.0.0.1", database.port or 5432)

    redis = urlparse(settings.redis_url)
    wait_for_tcp(redis.hostname or "127.0.0.1", redis.port or 6379)

    os.execvp(
        "uvicorn",
        [
            "uvicorn",
            "app.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
            "--workers",
            os.getenv("WEB_CONCURRENCY", "1"),
            "--no-access-log",
            "--ws-max-size",
            "65536",
        ],
    )


if __name__ == "__main__":
    main()
