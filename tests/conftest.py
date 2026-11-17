from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path

import psycopg
import pytest
import pytest_asyncio
from alembic.config import Config
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from psycopg import sql
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from alembic import command
from app.core.config import Settings
from app.core.sessions import MemorySessionStore
from app.main import create_app
from app.realtime.hub import MemoryLobbyHub

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
    settings = Settings(
        env="test",
        docs_enabled=True,
        public_url="http://testserver",
        require_verified_email=False,
        legacy_group_join_enabled=True,
        postgres_db=TEST_DATABASE,
        database_url=None,
    )
    url = make_url(settings.sqlalchemy_url)
    if settings.postgres_db != TEST_DATABASE or url.database != TEST_DATABASE:
        raise RuntimeError(f"Tests must use {TEST_DATABASE}, got {url.database}")
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
    return create_app(test_database, session_store=MemorySessionStore(), hub=MemoryLobbyHub())


@pytest_asyncio.fixture
async def client(app: FastAPI, test_database: Settings) -> AsyncIterator[AsyncClient]:
    _truncate_database(test_database)
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as http_client:
            yield http_client


@pytest_asyncio.fixture
async def db_session(app: FastAPI, test_database: Settings) -> AsyncIterator[AsyncSession]:
    _truncate_database(test_database)
    async with LifespanManager(app):
        async with app.state.sessionmaker() as session:
            yield session


@pytest.fixture
def movie_factory(test_database: Settings) -> Callable[..., int]:
    def create(**values: object) -> int:
        if not values:
            raise ValueError("movie_factory requires at least one column")
        columns = list(values)
        statement = sql.SQL("INSERT INTO public.movies ({}) VALUES ({}) RETURNING id").format(
            sql.SQL(", ").join(sql.Identifier(column) for column in columns),
            sql.SQL(", ").join(sql.Placeholder() for _ in columns),
        )
        with psycopg.connect(_database_url(test_database), autocommit=True) as connection:
            row = connection.execute(statement, list(values.values())).fetchone()
        if row is None:
            raise RuntimeError("movie_factory insert did not return an id")
        return int(row[0])

    return create


@pytest.fixture
def sync_session(test_database: Settings) -> Iterator[Session]:
    _truncate_database(test_database)
    engine = create_engine(test_database.sqlalchemy_url, pool_pre_ping=True)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture
def user_factory(test_database: Settings) -> Callable[..., int]:
    def create(username: str) -> int:
        with psycopg.connect(_database_url(test_database), autocommit=True) as connection:
            row = connection.execute(
                "INSERT INTO users (username, password_hash) VALUES (%s, %s) RETURNING id",
                (username, "unused"),
            ).fetchone()
        if row is None:
            raise RuntimeError("user_factory insert did not return an id")
        return int(row[0])

    return create


@pytest.fixture
def ws_client(app: FastAPI, test_database: Settings) -> Iterator[TestClient]:
    _truncate_database(test_database)
    with TestClient(app) as client:
        yield client
