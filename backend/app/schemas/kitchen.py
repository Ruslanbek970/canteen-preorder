from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, Field

from app.models import OrderChannel, OrderStatus, WasteReason


class KitchenLine(BaseModel):
    menu_item_id: int
    name: str
    quantity: int


class KitchenOrder(BaseModel):
    id: int
    order_number: str
    status: OrderStatus
    channel: OrderChannel
    pickup_slot_id: int | None
    pickup_shelf: int | None
    paid_at: datetime | None
    items: list[KitchenLine]
    # The only allergy information staff see (SPEC 6): «АЛЛЕРГИЯ: ОРЕХИ, МОЛОКО».
    allergy_flag: str | None


class BoardSlot(BaseModel):
    slot_id: int | None
    starts_at: time | None
    ends_at: time | None
    orders: list[KitchenOrder]


class KitchenBoard(BaseModel):
    canteen_id: int
    date: date
    slots: list[BoardSlot]
    counts: dict[str, int]


class PrepLine(BaseModel):
    name: str
    quantity: int


class PrepSlot(BaseModel):
    slot_id: int
    starts_at: time
    ends_at: time
    orders: int
    items: list[PrepLine]


class PrepSummary(BaseModel):
    canteen_id: int
    date: date
    slots: list[PrepSlot]


class StatusChange(BaseModel):
    status: Literal[OrderStatus.cooking, OrderStatus.ready]


class SlotStartResult(BaseModel):
    slot_id: int
    order_ids: list[int]


class Label(BaseModel):
    order_id: int
    order_number: str
    canteen_name: str
    service_date: date
    starts_at: time | None
    ends_at: time | None
    items: list[KitchenLine]
    allergy_flag: str | None


class WasteIn(BaseModel):
    menu_item_id: int
    portions: int = Field(gt=0, le=1000)
    reason: Literal[WasteReason.expired, WasteReason.damaged, WasteReason.other]


class WasteOut(BaseModel):
    id: int
    menu_item_id: int
    dish_name: str
    portions: int
    reason: WasteReason
    recorded_at: datetime


class CloseDayResult(BaseModel):
    date: date
    written_off: list[WasteOut]
    kept: list[PrepLine]  # leftovers that keep until tomorrow (shelf life >= 24 h)
