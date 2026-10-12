from app.config import get_settings
from app.errors import NotFoundError
from app.payments.base import PaymentIntent, PaymentProvider, WebhookResult
from app.payments.mock import MockPaymentProvider

PROVIDERS: dict[str, type[PaymentProvider]] = {"mock": MockPaymentProvider}


def get_provider(name: str | None = None) -> PaymentProvider:
    name = name or get_settings().payment_provider
    cls = PROVIDERS.get(name)
    if cls is None:
        raise NotFoundError("payment_provider", f"Unknown payment provider {name}")
    return cls()


__all__ = ["PaymentIntent", "PaymentProvider", "WebhookResult", "get_provider"]
