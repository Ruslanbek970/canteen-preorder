from datetime import datetime, time
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.models import OrderStatus, PaymentMethod
from app.schemas.kitchen import KitchenLine


class PickupOrder(BaseModel):
    id: int
    order_number: str
    status: OrderStatus
    pickup_shelf: int | None
    starts_at: time | None
    ends_at: time | None
    customer_name: str | None
    items: list[KitchenLine]
    total: Decimal
    allergy_flag: str | None
    picked_up_at: datetime | None


class PosLine(BaseModel):
    menu_item_id: int
    quantity: int = Field(ge=1, le=10)


class PosSale(BaseModel):
    items: list[PosLine] = Field(min_length=1, max_length=10)
    method: Literal[PaymentMethod.cash, PaymentMethod.kaspi_qr]


class PosReceipt(BaseModel):
    order_id: int
    order_number: str
    method: PaymentMethod
    subtotal: Decimal
    discount_total: Decimal
    total: Decimal
    fiscal_receipt_number: str | None
    items: list[KitchenLine]
