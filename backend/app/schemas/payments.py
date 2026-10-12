from decimal import Decimal

from pydantic import BaseModel

from app.models import PaymentMethod, PaymentStatus


class PaymentOut(BaseModel):
    id: int
    order_id: int
    order_number: str
    canteen_name: str
    method: PaymentMethod
    amount: Decimal
    status: PaymentStatus
    url: str | None
    fiscal_receipt_number: str | None
