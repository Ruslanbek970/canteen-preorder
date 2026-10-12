from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

_settings = get_settings()
# CURRENT_DATE and now() in views and defaults must follow the canteen time zone.
engine = create_engine(
    _settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    connect_args={"options": f"-c timezone={_settings.tz}"},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def set_current_user(db: Session, user_id: int | None) -> None:
    """SET LOCAL app.current_user_id for the status-history trigger (SPEC 5.3)."""
    db.execute(
        text("SELECT set_config('app.current_user_id', :uid, true)"),
        {"uid": "" if user_id is None else str(user_id)},
    )


def check_db() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
