from datetime import date, datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampTZ, int_pk, smallint_pk
from app.models.enums import AllergySeverity, allergy_severity


class DishCategory(Base):
    __tablename__ = "dish_categories"

    id: Mapped[int] = smallint_pk()
    name: Mapped[str] = mapped_column(sa.String(50), nullable=False, unique=True)
    sort_order: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False, server_default="0")


class Allergen(Base):
    __tablename__ = "allergens"

    id: Mapped[int] = smallint_pk()
    code: Mapped[str] = mapped_column(sa.String(30), nullable=False, unique=True)
    name_ru: Mapped[str] = mapped_column(sa.String(60), nullable=False)
    name_kk: Mapped[str | None] = mapped_column(sa.String(60))


class IngredientAllergen(Base):
    __tablename__ = "ingredient_allergens"

    ingredient_id: Mapped[int] = mapped_column(
        sa.ForeignKey("ingredients.id", ondelete="CASCADE"), primary_key=True
    )
    allergen_id: Mapped[int] = mapped_column(sa.ForeignKey("allergens.id"), primary_key=True)


class Ingredient(Base):
    __tablename__ = "ingredients"
    __table_args__ = (sa.CheckConstraint("unit IN ('g', 'ml', 'pcs')", name="unit"),)

    id: Mapped[int] = int_pk()
    name: Mapped[str] = mapped_column(sa.String(100), nullable=False, unique=True)
    unit: Mapped[str] = mapped_column(sa.String(5), nullable=False)

    allergens: Mapped[list[Allergen]] = relationship(
        secondary="ingredient_allergens", order_by="Allergen.id"
    )


class DishIngredient(Base):
    __tablename__ = "dish_ingredients"
    __table_args__ = (sa.CheckConstraint("quantity > 0", name="quantity"),)

    dish_id: Mapped[int] = mapped_column(
        sa.ForeignKey("dishes.id", ondelete="CASCADE"), primary_key=True
    )
    ingredient_id: Mapped[int] = mapped_column(sa.ForeignKey("ingredients.id"), primary_key=True)
    quantity: Mapped[Decimal] = mapped_column(sa.Numeric(8, 2), nullable=False)

    ingredient: Mapped[Ingredient] = relationship()


class Dish(Base):
    __tablename__ = "dishes"
    __table_args__ = (
        sa.CheckConstraint("base_price > 0", name="base_price"),
        sa.CheckConstraint("portion_grams > 0", name="portion_grams"),
        sa.CheckConstraint("calories >= 0", name="calories"),
        sa.CheckConstraint("shelf_life_hours > 0", name="shelf_life_hours"),
    )

    id: Mapped[int] = int_pk()
    category_id: Mapped[int] = mapped_column(sa.ForeignKey("dish_categories.id"), nullable=False)
    name_ru: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    name_kk: Mapped[str | None] = mapped_column(sa.String(120))
    description: Mapped[str | None] = mapped_column(sa.Text)
    base_price: Mapped[Decimal] = mapped_column(sa.Numeric(10, 2), nullable=False)
    portion_grams: Mapped[int | None] = mapped_column(sa.SmallInteger)
    calories: Mapped[int | None] = mapped_column(sa.SmallInteger)
    protein_g: Mapped[Decimal | None] = mapped_column(sa.Numeric(5, 1))
    fat_g: Mapped[Decimal | None] = mapped_column(sa.Numeric(5, 1))
    carbs_g: Mapped[Decimal | None] = mapped_column(sa.Numeric(5, 1))
    shelf_life_hours: Mapped[int] = mapped_column(
        sa.SmallInteger, nullable=False, server_default="4"
    )
    is_halal: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.true())
    is_vegetarian: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.false()
    )
    photo_url: Mapped[str | None] = mapped_column(sa.String(255))
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.true())

    category: Mapped[DishCategory] = relationship()
    recipe: Mapped[list[DishIngredient]] = relationship(
        cascade="all, delete-orphan", order_by="DishIngredient.ingredient_id"
    )


class UserAllergen(Base):
    __tablename__ = "user_allergens"

    user_id: Mapped[int] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    allergen_id: Mapped[int] = mapped_column(sa.ForeignKey("allergens.id"), primary_key=True)
    severity: Mapped[AllergySeverity] = mapped_column(
        allergy_severity, nullable=False, server_default=AllergySeverity.moderate.value
    )

    allergen: Mapped[Allergen] = relationship()


class MenuItem(Base):
    __tablename__ = "menu_items"
    __table_args__ = (
        sa.CheckConstraint("price > 0", name="price"),
        sa.CheckConstraint("forecast_portions >= 0", name="forecast_portions"),
        sa.CheckConstraint("planned_portions >= 0", name="planned_portions"),
        sa.CheckConstraint("available_portions >= 0", name="available_portions"),
        sa.CheckConstraint("available_portions <= planned_portions", name="available_le_planned"),
        sa.UniqueConstraint("canteen_id", "dish_id", "menu_date"),
        sa.Index("idx_menu_items_day", "canteen_id", "menu_date"),
    )

    id: Mapped[int] = int_pk()
    canteen_id: Mapped[int] = mapped_column(sa.ForeignKey("canteens.id"), nullable=False)
    dish_id: Mapped[int] = mapped_column(sa.ForeignKey("dishes.id"), nullable=False)
    menu_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    price: Mapped[Decimal] = mapped_column(sa.Numeric(10, 2), nullable=False)
    forecast_portions: Mapped[int | None] = mapped_column(sa.SmallInteger)
    forecast_model: Mapped[str | None] = mapped_column(sa.String(30))
    planned_portions: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)
    available_portions: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)
    cooked_at: Mapped[datetime | None] = mapped_column(TimestampTZ)

    dish: Mapped[Dish] = relationship()
