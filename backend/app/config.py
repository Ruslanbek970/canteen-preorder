from datetime import date
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "dev-insecure-jwt-secret-change-me"


class Settings(BaseSettings):
    """Application settings loaded from environment variables (see .env.example)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "dev"
    tz: str = "Asia/Almaty"

    database_url: str = "postgresql+psycopg://canteen:canteen@db:5432/canteen"
    redis_url: str = "redis://redis:6379/0"
    # Connections per API process. Sync endpoints run in a thread pool that is capped to the same
    # number (app.main), so a request never waits for a connection while holding a thread that
    # another request needs to give its connection back. Processes x total < max_connections.
    db_pool_size: int = 10
    db_max_overflow: int = 10
    # The worker serves its Prometheus metrics here (SPEC 14.8).
    worker_metrics_port: int = 9100

    jwt_secret: str = ""
    access_token_minutes: int = 15
    refresh_token_days: int = 30

    allowed_email_domains: str = "demo.kz,uni.kz"
    frontend_url: str = "http://localhost:5173"

    smtp_host: str = "mailpit"
    smtp_port: int = 1025
    smtp_from: str = "noreply@canteen.local"
    # Production mail servers want a login and STARTTLS (port 587); Mailpit needs neither.
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_starttls: bool = False

    telegram_bot_token: str = ""
    telegram_bot_username: str = ""
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = "mailto:admin@canteen.local"

    payment_provider: str = "mock"
    unpaid_order_timeout_minutes: int = 10
    no_show_after_minutes: int = 30
    paid_cancel_before_slot_minutes: int = 30
    verification_code_minutes: int = 30

    # Rate limits (SPEC 12); switched off in tests that hammer endpoints.
    rate_limit_enabled: bool = True
    login_attempts_per_minute: int = 5
    orders_per_minute: int = 10

    # Dev convenience: run migrations and load demo data on first start of an empty database.
    auto_seed: bool = False

    # Forecast features (SPEC 7.13): semester start and holiday / exam-session dates.
    semester_start: date = date(2026, 9, 1)
    holidays: str = ""

    sentry_dsn: str = ""
    log_json: bool = True

    @property
    def cors_origins(self) -> list[str]:
        return [self.frontend_url]

    @property
    def email_domains(self) -> set[str]:
        return {d.strip().lower() for d in self.allowed_email_domains.split(",") if d.strip()}

    @property
    def jwt_key(self) -> str:
        if self.jwt_secret:
            return self.jwt_secret
        if self.app_env == "prod":
            raise RuntimeError("JWT_SECRET must be set in production")
        return DEV_JWT_SECRET

    @property
    def holiday_dates(self) -> set[date]:
        return {date.fromisoformat(d.strip()) for d in self.holidays.split(",") if d.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
