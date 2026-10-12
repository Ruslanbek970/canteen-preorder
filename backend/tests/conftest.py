"""Test setup: a separate `<db>_test` database migrated once per session and truncated before
every test, Redis database 15, and helpers to create data and log in."""

import os

from sqlalchemy.engine import make_url


def _test_database_url() -> str:
    url = make_url(
        os.environ.get("DATABASE_URL", "postgresql+psycopg://canteen:canteen@db/canteen")
    )
    if not (url.database or "").endswith("_test"):
        url = url.set(database=f"{url.database}_test")
    return url.render_as_string(hide_password=False)


def _test_redis_url() -> str:
    base = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    return base.rsplit("/", 1)[0] + "/15"


os.environ["DATABASE_URL"] = _test_database_url()
os.environ["REDIS_URL"] = _test_redis_url()
os.environ["APP_ENV"] = "test"
os.environ["AUTO_SEED"] = "false"
os.environ["LOG_JSON"] = "false"

from collections.abc import Iterator  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from tests.factories import Factory  # noqa: E402


def _ensure_database(url: str) -> None:
    target = make_url(url)
    admin = create_engine(target.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": target.database}
        )
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{target.database}"'))
    admin.dispose()


def _migrate_fresh() -> None:
    from alembic import command
    from alembic.config import Config

    from app.db import engine

    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "alembic"))
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session", autouse=True)
def _database() -> Iterator[None]:
    _ensure_database(os.environ["DATABASE_URL"])
    _migrate_fresh()
    yield


@pytest.fixture(autouse=True)
def _clean_state(_database: None) -> Iterator[None]:
    from app.db import engine
    from app.models import Base
    from app.redis_client import get_redis

    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    get_redis().flushdb()
    yield


@pytest.fixture
def outbox(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, str]]:
    sent: list[dict[str, str]] = []

    def fake_send(to: str, subject: str, body: str) -> bool:
        sent.append({"to": to, "subject": subject, "body": body})
        return True

    monkeypatch.setattr("app.services.auth.send_email", fake_send)
    return sent


@pytest.fixture
def db() -> Iterator[Session]:
    from app.db import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(outbox: list[dict[str, str]]) -> Iterator[TestClient]:
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def factory(db: Session) -> Factory:
    return Factory(db)


@pytest.fixture
def auth(client: TestClient):
    """auth(user) -> Authorization headers for that user."""
    from app.security import create_access_token

    def headers(user) -> dict[str, str]:
        return {"Authorization": f"Bearer {create_access_token(user)}"}

    return headers


@pytest.fixture
def freeze(monkeypatch: pytest.MonkeyPatch):
    """freeze("2026-10-12 11:00") pins the app clock to that Asia/Almaty wall time."""
    from datetime import datetime

    from app.utils import time as clock

    def _freeze(local: str):
        moment = datetime.fromisoformat(local).replace(tzinfo=clock.local_tz())
        monkeypatch.setattr(clock, "now_utc", lambda: moment.astimezone(clock.UTC))
        return moment

    return _freeze
