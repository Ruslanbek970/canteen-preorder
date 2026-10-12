"""Container start-up: apply migrations, and in dev load demo data into an empty database.

python -m scripts.bootstrap
"""

import logging

from alembic import command
from alembic.config import Config
from sqlalchemy import func, select

from app.config import get_settings
from app.db import SessionLocal
from app.models import User

log = logging.getLogger("bootstrap")


def migrate() -> None:
    cfg = Config("alembic.ini")
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "head")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    migrate()
    log.info("migrations applied")
    if not get_settings().auto_seed:
        return
    with SessionLocal() as db:
        has_users = db.scalar(select(func.count(User.id))) or 0
    if has_users:
        log.info("database already has data, demo seed skipped")
        return
    from scripts import seed

    seed.main()


if __name__ == "__main__":
    main()
