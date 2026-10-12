import os

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.db import engine


def _config() -> Config:
    here = os.path.dirname(__file__)
    cfg = Config(os.path.join(here, "..", "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(here, "..", "alembic"))
    cfg.attributes["configure_logger"] = False
    return cfg


def test_downgrade_base_and_upgrade_head():
    cfg = _config()
    command.downgrade(cfg, "base")
    assert set(inspect(engine).get_table_names()) <= {"alembic_version"}
    command.upgrade(cfg, "head")
    tables = set(inspect(engine).get_table_names())
    assert {"orders", "daily_counters", "refresh_tokens", "forecast_runs"} <= tables
    assert len(tables - {"alembic_version"}) == 26
    views = set(inspect(engine).get_view_names())
    assert views == {"v_dish_allergens", "v_menu_today", "v_kitchen_board"}
