from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models import AllergySeverity, UserRole


class MeResponse(BaseModel):
    id: int
    full_name: str
    email: str
    phone: str | None
    role: UserRole
    canteen_id: int | None
    canteen_name: str | None
    group_id: int | None
    group_code: str | None
    preferred_language: str
    email_verified: bool
    health_data_consent_at: datetime | None
    loyalty_points: int
    telegram_linked: bool
    marketing_opt_out: bool
    no_show_count_30d: int = 0


class MeUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=150)
    preferred_language: Literal["ru", "kk", "en"] | None = None
    group_id: int | None = None
    marketing_opt_out: bool | None = None


class UserAllergenIn(BaseModel):
    allergen_id: int
    severity: AllergySeverity = AllergySeverity.moderate


class UserAllergenOut(BaseModel):
    allergen_id: int
    code: str
    name_ru: str
    name_kk: str | None
    severity: AllergySeverity


class AllergensPut(BaseModel):
    consent: bool = Field(description="Consent to store health data (SPEC 7.3)")
    allergens: list[UserAllergenIn] = Field(default_factory=list, max_length=20)


class MyAllergensResponse(BaseModel):
    health_data_consent_at: datetime | None
    allergens: list[UserAllergenOut]
