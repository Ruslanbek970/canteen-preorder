"""Menu of the day and dish cards for customers (SPEC 7.2)."""

from datetime import date, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.errors import NotFoundError, ValidationError
from app.models import (
    Canteen,
    Dish,
    DishCategory,
    DishIngredient,
    DishReview,
    MenuItem,
    OrderItem,
    User,
)
from app.schemas.menu import DishDetail, IngredientLine, MenuItemOut, MenuResponse, ReviewOut
from app.schemas.reference import AllergenOut
from app.services import allergens as allergy
from app.services import pricing
from app.utils import time as clock

TOMORROW_MENU_FROM = time(15, 0)
MIN_REVIEWS_FOR_RATING = 3


def available_dates() -> list[date]:
    """Today, and after 15:00 also tomorrow (SPEC 7.2)."""
    now = clock.now_local()
    days = [now.date()]
    if now.time() >= TOMORROW_MENU_FROM:
        days.append(now.date() + timedelta(days=1))
    return days


def dish_ratings(db: Session, dish_ids: list[int]) -> dict[int, tuple[float, int]]:
    if not dish_ids:
        return {}
    rows = db.execute(
        select(MenuItem.dish_id, func.avg(DishReview.rating), func.count(DishReview.id))
        .join(OrderItem, OrderItem.id == DishReview.order_item_id)
        .join(MenuItem, MenuItem.id == OrderItem.menu_item_id)
        .where(MenuItem.dish_id.in_(dish_ids))
        .group_by(MenuItem.dish_id)
    ).all()
    return {dish_id: (round(float(avg), 1), int(cnt)) for dish_id, avg, cnt in rows}


def _rating(ratings: dict[int, tuple[float, int]], dish_id: int) -> tuple[float | None, int]:
    avg, count = ratings.get(dish_id, (0.0, 0))
    return (avg if count >= MIN_REVIEWS_FOR_RATING else None), count


def get_canteen(db: Session, canteen_id: int) -> Canteen:
    canteen = db.get(Canteen, canteen_id)
    if canteen is None or not canteen.is_active:
        raise NotFoundError("canteen", "Столовая не найдена")
    return canteen


def menu_items_for(db: Session, canteen_id: int, day: date) -> list[MenuItem]:
    return list(
        db.scalars(
            select(MenuItem)
            .join(Dish, Dish.id == MenuItem.dish_id)
            .join(DishCategory, DishCategory.id == Dish.category_id)
            .options(joinedload(MenuItem.dish).joinedload(Dish.category))
            .where(MenuItem.canteen_id == canteen_id, MenuItem.menu_date == day, Dish.is_active)
            .order_by(DishCategory.sort_order, Dish.name_ru)
        )
    )


def get_menu(db: Session, canteen_id: int, day: date | None, user: User | None) -> MenuResponse:
    get_canteen(db, canteen_id)
    days = available_dates()
    day = day or days[0]
    if day not in days:
        raise ValidationError(
            "menu_date_unavailable",
            "Меню на эту дату пока недоступно",
            {"available_dates": [d.isoformat() for d in days]},
        )
    items = menu_items_for(db, canteen_id, day)
    dish_ids = [mi.dish_id for mi in items]
    allergens_by_dish = allergy.dish_allergens(db, dish_ids)
    mine = allergy.user_allergies(db, user)
    promos = pricing.item_promotions(db, [mi.id for mi in items], clock.now_utc())
    ratings = dish_ratings(db, dish_ids)
    out = []
    for mi in items:
        dish = mi.dish
        allergen_list = allergens_by_dish.get(dish.id, [])
        check = allergy.assess(allergen_list, mine)
        promo = promos.get(mi.id)
        rating, count = _rating(ratings, dish.id)
        out.append(
            MenuItemOut(
                id=mi.id,
                dish_id=dish.id,
                name_ru=dish.name_ru,
                name_kk=dish.name_kk,
                description=dish.description,
                category_id=dish.category_id,
                category_name=dish.category.name,
                category_sort=dish.category.sort_order,
                price=mi.price,
                price_now=pricing.discounted(mi.price, promo.discount_percent if promo else None),
                discount_percent=promo.discount_percent if promo else None,
                promotion_id=promo.id if promo else None,
                available_portions=mi.available_portions,
                portion_grams=dish.portion_grams,
                calories=dish.calories,
                protein_g=dish.protein_g,
                fat_g=dish.fat_g,
                carbs_g=dish.carbs_g,
                is_halal=dish.is_halal,
                is_vegetarian=dish.is_vegetarian,
                photo_url=dish.photo_url,
                allergens=[AllergenOut.model_validate(a) for a in allergen_list],
                rating=rating,
                rating_count=count,
                unsafe_for_me=check.unsafe,
                warning_for_me=check.warning,
                my_allergens=[a.code for a in check.severe + check.other],
            )
        )
    return MenuResponse(canteen_id=canteen_id, date=day, available_dates=days, items=out)


def get_dish(db: Session, dish_id: int, user: User | None) -> DishDetail:
    dish = db.get(Dish, dish_id, options=[joinedload(Dish.category)])
    if dish is None:
        raise NotFoundError("dish", "Блюдо не найдено")
    lines = db.scalars(
        select(DishIngredient)
        .options(joinedload(DishIngredient.ingredient))
        .where(DishIngredient.dish_id == dish.id)
        .order_by(DishIngredient.quantity.desc())
    ).all()
    allergen_list = allergy.dish_allergens(db, [dish.id]).get(dish.id, [])
    check = allergy.assess(allergen_list, allergy.user_allergies(db, user))
    rating, count = _rating(dish_ratings(db, [dish.id]), dish.id)
    reviews = db.execute(
        select(DishReview.rating, DishReview.comment, DishReview.created_at)
        .join(OrderItem, OrderItem.id == DishReview.order_item_id)
        .join(MenuItem, MenuItem.id == OrderItem.menu_item_id)
        .where(MenuItem.dish_id == dish.id)
        .order_by(DishReview.created_at.desc())
        .limit(5)
    ).all()
    return DishDetail(
        id=dish.id,
        name_ru=dish.name_ru,
        name_kk=dish.name_kk,
        description=dish.description,
        category_id=dish.category_id,
        category_name=dish.category.name,
        base_price=dish.base_price,
        portion_grams=dish.portion_grams,
        calories=dish.calories,
        protein_g=dish.protein_g,
        fat_g=dish.fat_g,
        carbs_g=dish.carbs_g,
        shelf_life_hours=dish.shelf_life_hours,
        is_halal=dish.is_halal,
        is_vegetarian=dish.is_vegetarian,
        photo_url=dish.photo_url,
        is_active=dish.is_active,
        ingredients=[
            IngredientLine(
                ingredient_id=line.ingredient_id,
                name=line.ingredient.name,
                unit=line.ingredient.unit,
                quantity=line.quantity,
            )
            for line in lines
        ],
        allergens=[AllergenOut.model_validate(a) for a in allergen_list],
        rating=rating,
        rating_count=count,
        reviews=[ReviewOut(rating=r, comment=c, created_at=t) for r, c, t in reviews],
        unsafe_for_me=check.unsafe,
        warning_for_me=check.warning,
    )
