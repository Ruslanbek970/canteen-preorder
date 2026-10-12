from typing import Annotated, Any

from fastapi import APIRouter, Body

from app.api.deps import DB, Customer
from app.schemas.payments import PaymentOut
from app.services import payments

router = APIRouter(prefix="/payments", tags=["payments"])


@router.get("/{payment_id}", response_model=PaymentOut)
def get_payment(payment_id: int, user: Customer, db: DB) -> PaymentOut:
    return payments.get_payment(db, user, payment_id)


@router.post("/mock/{payment_id}/confirm", response_model=PaymentOut)
def mock_confirm(payment_id: int, user: Customer, db: DB) -> PaymentOut:
    return payments.mock_result(db, user, payment_id, succeeded=True)


@router.post("/mock/{payment_id}/fail", response_model=PaymentOut)
def mock_fail(payment_id: int, user: Customer, db: DB) -> PaymentOut:
    return payments.mock_result(db, user, payment_id, succeeded=False)


@router.post("/webhook/{provider}", status_code=204)
def provider_webhook(provider: str, db: DB, payload: Annotated[dict[str, Any], Body()]) -> None:
    """For a real provider later (SPEC 8.5). Signature checks belong to the provider class."""
    payments.webhook(db, provider, payload)
