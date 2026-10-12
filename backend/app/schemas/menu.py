from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.reference import AllergenOut


class MenuItemOut(BaseModel):
    id: int
    dish_id: int
    name_ru: str
    name_kk: str | None
    description: str | None
    category_id: int
    category_name: str
    category_sort: int
    price: Decimal
    price_now: Decimal
    discount_percent: int | None
    promotion_id: int | None
    available_portions: int
    portion_grams: int | None
    calories: int | None
    protein_g: Decimal | None
    fat_g: Decimal | None
    carbs_g: Decimal | None
    is_halal: bool
    is_vegetarian: bool
    photo_url: str | None
    allergens: list[AllergenOut]
    rating: float | None
    rating_count: int
    unsafe_for_me: bool = False
    warning_for_me: bool = False
    my_allergens: list[str] = Field(default_factory=list)


class MenuResponse(BaseModel):
    canteen_id: int
    date: date
    available_dates: list[date]
    items: list[MenuItemOut]


class IngredientLine(BaseModel):
    ingredient_id: int
    name: str
    unit: str
    quantity: Decimal


class ReviewOut(BaseModel):
    rating: int
    comment: str | None
    created_at: datetime


class DishDetail(BaseModel):
    id: int
    name_ru: str
    name_kk: str | None
    description: str | None
    category_id: int
    category_name: str
    base_price: Decimal
    portion_grams: int | None
    calories: int | None
    protein_g: Decimal | None
    fat_g: Decimal | None
    carbs_g: Decimal | None
    shelf_life_hours: int
    is_halal: bool
    is_vegetarian: bool
    photo_url: str | None
    is_active: bool
    ingredients: list[IngredientLine]
    allergens: list[AllergenOut]
    rating: float | None
    rating_count: int
    reviews: list[ReviewOut] = Field(default_factory=list)
    unsafe_for_me: bool = False
    warning_for_me: bool = False
