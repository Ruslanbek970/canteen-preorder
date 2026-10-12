from datetime import date, time

from pydantic import BaseModel, Field


class SlotOut(BaseModel):
    id: int
    slot_date: date
    starts_at: time
    ends_at: time
    capacity: int
    booked_count: int
    free: int
    is_closed: bool
    discount_percent: int | None = None
    promotion_id: int | None = None


class SlotsHidden(BaseModel):
    by_schedule: int = 0
    too_late: int = 0
    full: int = 0
    closed: int = 0


class SlotsResponse(BaseModel):
    canteen_id: int
    date: date
    slots: list[SlotOut]
    hidden: SlotsHidden
    total: int
    cutoff_minutes: int
    schedule_applied: bool


class SlotPatch(BaseModel):
    capacity: int | None = Field(default=None, gt=0, le=1000)
    is_closed: bool | None = None


class ManagerSlotsResponse(BaseModel):
    canteen_id: int
    date: date
    slots: list[SlotOut]
