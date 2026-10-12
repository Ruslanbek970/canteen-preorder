from datetime import date, datetime, time

from pydantic import BaseModel, Field

from app.models import PromotionStatus, PromotionType


class PromotionOut(BaseModel):
    id: int
    type: PromotionType
    status: PromotionStatus
    discount_percent: int
    valid_from: datetime
    valid_to: datetime
    created_by_system: bool
    created_at: datetime
    menu_item_id: int | None
    dish_name: str | None
    available_portions: int | None
    planned_portions: int | None
    pickup_slot_id: int | None
    slot_date: date | None
    slot_starts_at: time | None
    slot_ends_at: time | None
    slot_booked: int | None
    slot_capacity: int | None


class OffPeakCreate(BaseModel):
    pickup_slot_id: int
    discount_percent: int = Field(ge=5, le=50)
