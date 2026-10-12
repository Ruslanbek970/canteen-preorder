from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables (see .env.example)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "dev"
    tz: str = "Asia/Almaty"

    database_url: str = "postgresql+psycopg://canteen:canteen@db:5432/canteen"
    redis_url: str = "redis://redis:6379/0"

    jwt_secret: str = ""
    access_token_minutes: int = 15
    refresh_token_days: int = 30

    allowed_email_domains: str = "demo.kz,uni.kz"
    frontend_url: str = "http://localhost:5173"

    smtp_host: str = "mailpit"
    smtp_port: int = 1025
    smtp_from: str = "noreply@canteen.local"

    telegram_bot_token: str = ""
    vapid_public_key: str = ""
    vapid_private_key: str = ""

    payment_provider: str = "mock"
    unpaid_order_timeout_minutes: int = 10
    no_show_after_minutes: int = 30

    sentry_dsn: str = ""

    @property
    def cors_origins(self) -> list[str]:
        return [self.frontend_url]


@lru_cache
def get_settings() -> Settings:
    return Settings()
