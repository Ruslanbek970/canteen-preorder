from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.reference import AllergenOut


class RecipeLineIn(BaseModel):
    ingredient_id: int
    quantity: Decimal = Field(gt=0, max_digits=8, decimal_places=2)


class DishFields(BaseModel):
    category_id: int | None = None
    name_ru: str | None = Field(default=None, min_length=1, max_length=120)
    name_kk: str | None = Field(default=None, max_length=120)
    description: str | None = None
    base_price: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    portion_grams: int | None = Field(default=None, gt=0, lt=32768)
    calories: int | None = Field(default=None, ge=0, lt=32768)
    protein_g: Decimal | None = Field(default=None, ge=0, max_digits=5, decimal_places=1)
    fat_g: Decimal | None = Field(default=None, ge=0, max_digits=5, decimal_places=1)
    carbs_g: Decimal | None = Field(default=None, ge=0, max_digits=5, decimal_places=1)
    shelf_life_hours: int | None = Field(default=None, gt=0, lt=1000)
    is_halal: bool | None = None
    is_vegetarian: bool | None = None
    photo_url: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None
    ingredients: list[RecipeLineIn] | None = Field(default=None, max_length=50)


class DishCreate(DishFields):
    category_id: int
    name_ru: str = Field(min_length=1, max_length=120)
    base_price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    ingredients: list[RecipeLineIn] = Field(default_factory=list, max_length=50)


class DishUpdate(DishFields):
    pass


class RecipeLineOut(BaseModel):
    ingredient_id: int
    name: str
    unit: str
    quantity: Decimal


class DishOut(BaseModel):
    id: int
    category_id: int
    category_name: str
    name_ru: str
    name_kk: str | None
    description: str | None
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
    ingredients: list[RecipeLineOut]
    allergens: list[AllergenOut]


class IngredientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    unit: Literal["g", "ml", "pcs"]
    allergen_ids: list[int] = Field(default_factory=list, max_length=20)


class IngredientOut(BaseModel):
    id: int
    name: str
    unit: str
    allergens: list[AllergenOut]


class MenuPutItem(BaseModel):
    dish_id: int
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    planned_portions: int = Field(ge=0, le=5000)


class MenuPut(BaseModel):
    items: list[MenuPutItem] = Field(max_length=100)


class MenuItemPatch(BaseModel):
    price: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    planned_portions: int | None = Field(default=None, ge=0, le=5000)
    available_portions: int | None = Field(default=None, ge=0, le=5000)


class ManagerMenuItem(BaseModel):
    id: int
    dish_id: int
    dish_name: str
    category_name: str
    price: Decimal
    planned_portions: int
    available_portions: int
    sold_portions: int
    forecast_portions: int | None
    forecast_model: str | None
    cooked_at: datetime | None
    allergens: list[AllergenOut]


class ManagerMenu(BaseModel):
    canteen_id: int
    date: str
    items: list[ManagerMenuItem]
    synthetic_history: bool = True
