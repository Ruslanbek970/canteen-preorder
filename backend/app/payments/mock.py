import uuid
from typing import Any

from app.errors import ValidationError
from app.models import Payment
from app.payments.base import PaymentIntent, PaymentProvider, WebhookResult


class MockPaymentProvider(PaymentProvider):
    """The only provider in the project: the "payment page" is the frontend's /pay/mock/:id with
    «Оплатить» and «Отказ» buttons, which call the confirm/fail endpoints (imitating a webhook)."""

    name = "mock"

    def create_payment(self, payment: Payment) -> PaymentIntent:
        return PaymentIntent(url=f"/pay/mock/{payment.id}")

    def handle_webhook(self, payload: dict[str, Any]) -> WebhookResult:
        try:
            payment_id = int(payload["payment_id"])
            succeeded = bool(payload["succeeded"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValidationError("invalid_webhook", "Bad mock webhook payload") from exc
        return WebhookResult(payment_id, succeeded, f"mock-{uuid.uuid4().hex[:16]}")

    def refund(self, payment: Payment) -> bool:
        return True

    def fiscal_receipt_number(self, payment: Payment) -> str | None:
        return f"MOCK-{payment.id:08d}"
