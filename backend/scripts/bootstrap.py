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
from app.services import slots

log = logging.getLogger("bootstrap")


def migrate() -> None:
    cfg = Config("alembic.ini")
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "head")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    migrate()
    log.info("migrations applied")
    if get_settings().auto_seed:
        from scripts import seed

        with SessionLocal() as db:
            has_users = db.scalar(select(func.count(User.id))) or 0
        if has_users:
            with SessionLocal() as db:
                added = seed.ensure_demo_menu(db)
            log.info("demo seed skipped (data exists), %s demo menu items added", added)
            # Fills past weekdays without orders, so the 8-week history keeps up with the date.
            from ml import synthetic_history

            with SessionLocal() as db:
                days = synthetic_history.generate_for_active(db)
            log.info("synthetic history: %s days added", days)
            from ml import forecast

            with SessionLocal() as db:
                forecast.prepare_active(db)
            log.info("demand forecast ready")
        else:
            seed.main()
    # The worker regenerates slots daily at 05:00; this covers a fresh start.
    with SessionLocal() as db:
        created = slots.generate_for_active(db)
    log.info("pickup slots ensured for today and tomorrow (%s new)", created)


if __name__ == "__main__":
    main()
