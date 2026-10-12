"""Payment provider interface (SPEC 7.7). A real provider is a new class, services don't change."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from app.models import Payment


@dataclass
class PaymentIntent:
    url: str


@dataclass
class WebhookResult:
    payment_id: int
    succeeded: bool
    transaction_id: str | None = None


class PaymentProvider(ABC):
    name: str

    @abstractmethod
    def create_payment(self, payment: Payment) -> PaymentIntent: ...

    @abstractmethod
    def handle_webhook(self, payload: dict[str, Any]) -> WebhookResult: ...

    @abstractmethod
    def refund(self, payment: Payment) -> bool: ...

    def fiscal_receipt_number(self, payment: Payment) -> str | None:
        return None
