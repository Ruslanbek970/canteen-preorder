import uuid
from datetime import date, datetime, time
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models import OrderChannel, OrderStatus


class OrderItemIn(BaseModel):
    menu_item_id: int
    quantity: int = Field(ge=1, le=10)


class OrderCreate(BaseModel):
    canteen_id: int
    pickup_slot_id: int
    items: list[OrderItemIn] = Field(min_length=1, max_length=10)
    allergy_warning_ack: bool = False


class OrderItemOut(BaseModel):
    id: int
    menu_item_id: int
    dish_id: int
    name_ru: str
    name_kk: str | None
    quantity: int
    unit_price: Decimal
    discount_amount: Decimal
    line_total: Decimal
    promotion_id: int | None


class OrderSlotOut(BaseModel):
    id: int
    slot_date: date
    starts_at: time
    ends_at: time


class OrderOut(BaseModel):
    id: int
    order_number: str
    canteen_id: int
    canteen_name: str
    service_date: date
    channel: OrderChannel
    status: OrderStatus
    pickup_slot: OrderSlotOut | None
    subtotal: Decimal
    discount_total: Decimal
    total: Decimal
    qr_token: uuid.UUID
    pickup_shelf: int | None
    allergy_warning_ack: bool
    created_at: datetime
    paid_at: datetime | None
    ready_at: datetime | None
    picked_up_at: datetime | None
    items: list[OrderItemOut]
    payment_id: int | None = None
    payment_url: str | None = None
    pay_until: datetime | None = None
    can_cancel: bool = False
    cancel_until: datetime | None = None
    no_show_warning: bool = False


class OrderList(BaseModel):
    items: list[OrderOut]
    total: int


class CartLine(BaseModel):
    menu_item_id: int
    dish_id: int
    name_ru: str
    name_kk: str | None
    price: Decimal
    discount_percent: int | None
    quantity: int
    available_portions: int
    warning_for_me: bool


class SkippedLine(BaseModel):
    dish_id: int
    name_ru: str
    reason: str  # not_on_menu | sold_out | allergy


class RepeatResponse(BaseModel):
    canteen_id: int
    date: date
    items: list[CartLine]
    skipped: list[SkippedLine]
