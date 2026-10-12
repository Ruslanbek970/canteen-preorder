from datetime import time

from app.schemas.common import ORMModel


class CanteenOut(ORMModel):
    id: int
    name: str
    building_id: int
    opens_at: time
    closes_at: time
    slug: str | None
    is_active: bool
    order_cutoff_minutes: int


class GroupOut(ORMModel):
    id: int
    code: str
    faculty: str | None
    study_year: int | None


class AllergenOut(ORMModel):
    id: int
    code: str
    name_ru: str
    name_kk: str | None


class CategoryOut(ORMModel):
    id: int
    name: str
    sort_order: int


class BuildingOut(ORMModel):
    id: int
    name: str
    address: str | None
