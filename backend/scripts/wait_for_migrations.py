"""The worker starts after the backend has applied migrations (bootstrap runs them).

python -m scripts.wait_for_migrations
"""

import logging
import time

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from app.db import engine

log = logging.getLogger("wait_for_migrations")


def current_revision() -> str | None:
    try:
        with engine.connect() as conn:
            return conn.scalar(text("SELECT version_num FROM alembic_version"))
    except Exception:
        return None


def main(timeout_seconds: int = 300) -> None:
    logging.basicConfig(level=logging.INFO)
    head = ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()
    deadline = time.monotonic() + timeout_seconds
    while current_revision() != head:
        if time.monotonic() > deadline:
            raise SystemExit(f"database is not at migration {head}")
        log.info("waiting for migrations (%s)", head)
        time.sleep(2)


if __name__ == "__main__":
    main()
