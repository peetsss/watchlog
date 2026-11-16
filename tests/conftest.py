from collections.abc import AsyncIterator
from pathlib import Path

import psycopg
import pytest
import pytest_asyncio
from alembic.config import Config
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from psycopg import sql
from sqlalchemy.engine import make_url

from alembic import command
from app.core.config import Settings
from app.core.sessions import MemorySessionStore
from app.main import create_app

ROOT = Path(__file__).resolve().parents[1]
TEST_DATABASE = "watchlog_test"
FORBIDDEN_DATABASES = frozenset({"watchlog_db", "watchlog_v2"})


def _database_url(settings: Settings) -> str:
    return make_url(settings.sqlalchemy_url).set(drivername="postgresql").render_as_string(hide_password=False)


def _admin_url(settings: Settings) -> str:
    return (
        make_url(settings.sqlalchemy_url)
        .set(drivername="postgresql", database="postgres")
        .render_as_string(hide_password=False)
    )


def _create_database(settings: Settings) -> None:
    with psycopg.connect(_admin_url(settings), autocommit=True) as connection:
        exists = connection.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (settings.postgres_db,),
        ).fetchone()
        if exists is None:
            connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(settings.postgres_db)))


def _run_migrations(settings: Settings) -> None:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", settings.sqlalchemy_url)
    config.attributes["configure_logging"] = False
    command.upgrade(config, "head")


def _truncate_database(settings: Settings) -> None:
    with psycopg.connect(_database_url(settings), autocommit=True) as connection:
        rows = connection.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename <> 'alembic_version'"
        ).fetchall()
        tables = [row[0] for row in rows]
        if not tables:
            return
        statement = sql.SQL("TRUNCATE TABLE {} RESTART IDENTITY CASCADE").format(
            sql.SQL(", ").join(sql.Identifier(table) for table in tables)
        )
        connection.execute(statement)


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    settings = Settings(env="test", docs_enabled=True, postgres_db=TEST_DATABASE)
    if settings.postgres_db != TEST_DATABASE:
        raise RuntimeError(f"Tests must use {TEST_DATABASE}, got {settings.postgres_db}")
    if settings.postgres_db in FORBIDDEN_DATABASES:
        raise RuntimeError(f"Refusing to run tests against {settings.postgres_db}")
    return settings


@pytest.fixture(scope="session")
def test_database(test_settings: Settings) -> Settings:
    _create_database(test_settings)
    _run_migrations(test_settings)
    return test_settings


@pytest.fixture
def app(test_database: Settings) -> FastAPI:
    return create_app(test_database, session_store=MemorySessionStore())


@pytest_asyncio.fixture
async def client(app: FastAPI, test_database: Settings) -> AsyncIterator[AsyncClient]:
    _truncate_database(test_database)
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as http_client:
            yield http_client
