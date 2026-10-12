from datetime import datetime, time

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.models import UserRole
from app.schemas.common import ORMModel


class AdminUserOut(BaseModel):
    """No health data here: allergies are visible to their owner only (SPEC 6)."""

    id: int
    full_name: str
    email: str
    phone: str | None
    role: UserRole
    group_id: int | None
    group_code: str | None
    canteen_id: int | None
    canteen_name: str | None
    is_active: bool
    email_verified: bool
    created_at: datetime


class AdminUserList(BaseModel):
    items: list[AdminUserOut]
    total: int


class AdminUserCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: UserRole
    phone: str | None = Field(default=None, max_length=20)
    canteen_id: int | None = None
    group_id: int | None = None


class AdminUserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=150)
    phone: str | None = Field(default=None, max_length=20)
    role: UserRole | None = None
    canteen_id: int | None = None
    group_id: int | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


class CanteenAdminOut(ORMModel):
    id: int
    building_id: int
    name: str
    slug: str | None
    opens_at: time
    closes_at: time
    default_slot_minutes: int
    default_slot_capacity: int
    pickup_shelves_count: int
    order_cutoff_minutes: int
    is_active: bool


class CanteenFields(BaseModel):
    building_id: int | None = None
    name: str | None = Field(default=None, min_length=2, max_length=100)
    slug: str | None = Field(default=None, max_length=50, pattern=r"^[a-z0-9-]+$")
    opens_at: time | None = None
    closes_at: time | None = None
    default_slot_minutes: int | None = Field(default=None, ge=5, le=60)
    default_slot_capacity: int | None = Field(default=None, ge=1, le=500)
    pickup_shelves_count: int | None = Field(default=None, ge=1, le=100)
    order_cutoff_minutes: int | None = Field(default=None, ge=0, le=240)
    is_active: bool | None = None


class CanteenCreate(CanteenFields):
    building_id: int
    name: str = Field(min_length=2, max_length=100)
    opens_at: time
    closes_at: time

    @model_validator(mode="after")
    def hours(self) -> "CanteenCreate":
        if self.opens_at >= self.closes_at:
            raise ValueError("opens_at must be before closes_at")
        return self


class CanteenUpdate(CanteenFields):
    pass


class BuildingCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    address: str | None = Field(default=None, max_length=255)


class GroupCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    faculty: str | None = Field(default=None, max_length=100)
    study_year: int | None = Field(default=None, ge=1, le=6)


class ScheduleRowError(BaseModel):
    line: int
    code: str
    message: str


class ScheduleImportResult(BaseModel):
    rows: int
    groups: list[str]
    errors: list[ScheduleRowError]
    imported: bool
    deleted: int
    created: int


class GroupAdminOut(BaseModel):
    id: int
    code: str
    faculty: str | None
    study_year: int | None
    students: int
    lessons: int
