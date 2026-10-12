"""Dishes, recipes, ingredients and the menu of a day for the canteen manager (SPEC 8.8)."""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.errors import ConflictError, NotFoundError, ValidationError
from app.models import (
    Allergen,
    Dish,
    DishCategory,
    DishIngredient,
    Ingredient,
    IngredientAllergen,
    MenuItem,
    Order,
    OrderItem,
    OrderStatus,
)
from app.schemas.catalog import (
    DishCreate,
    DishOut,
    DishUpdate,
    IngredientCreate,
    IngredientOut,
    ManagerMenu,
    ManagerMenuItem,
    MenuItemPatch,
    MenuPut,
    RecipeLineIn,
    RecipeLineOut,
)
from app.schemas.reference import AllergenOut
from app.services import allergens as allergy

# ---- dishes ---------------------------------------------------------------


def _dish_out(db: Session, dish: Dish, allergens: list[Allergen] | None = None) -> DishOut:
    if allergens is None:
        allergens = allergy.dish_allergens(db, [dish.id]).get(dish.id, [])
    return DishOut(
        id=dish.id,
        category_id=dish.category_id,
        category_name=dish.category.name,
        name_ru=dish.name_ru,
        name_kk=dish.name_kk,
        description=dish.description,
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
            RecipeLineOut(
                ingredient_id=line.ingredient_id,
                name=line.ingredient.name,
                unit=line.ingredient.unit,
                quantity=line.quantity,
            )
            for line in dish.recipe
        ],
        allergens=[AllergenOut.model_validate(a) for a in allergens],
    )


def _load_dish(db: Session, dish_id: int) -> Dish:
    dish = db.get(
        Dish,
        dish_id,
        options=[
            joinedload(Dish.category),
            joinedload(Dish.recipe).joinedload(DishIngredient.ingredient),
        ],
        populate_existing=True,
    )
    if dish is None:
        raise NotFoundError("dish", "Блюдо не найдено")
    return dish


def list_dishes(db: Session, include_inactive: bool = True) -> list[DishOut]:
    query = (
        select(Dish)
        .options(
            joinedload(Dish.category),
            joinedload(Dish.recipe).joinedload(DishIngredient.ingredient),
        )
        .order_by(Dish.name_ru)
    )
    if not include_inactive:
        query = query.where(Dish.is_active)
    dishes = list(db.scalars(query).unique())
    by_dish = allergy.dish_allergens(db, [d.id for d in dishes])
    return [_dish_out(db, d, by_dish.get(d.id, [])) for d in dishes]


def get_dish(db: Session, dish_id: int) -> DishOut:
    return _dish_out(db, _load_dish(db, dish_id))


def _check_recipe(db: Session, lines: list[RecipeLineIn]) -> None:
    ids = [line.ingredient_id for line in lines]
    if len(ids) != len(set(ids)):
        raise ValidationError("duplicate_ingredient", "Ингредиент указан дважды")
    if ids:
        known = set(db.scalars(select(Ingredient.id).where(Ingredient.id.in_(ids))))
        missing = sorted(set(ids) - known)
        if missing:
            raise ValidationError(
                "ingredient_not_found", "Ингредиент не найден", {"ingredient_ids": missing}
            )


def _check_category(db: Session, category_id: int) -> None:
    if db.get(DishCategory, category_id) is None:
        raise ValidationError("category_not_found", "Категория не найдена")


def create_dish(db: Session, data: DishCreate) -> DishOut:
    _check_category(db, data.category_id)
    _check_recipe(db, data.ingredients)
    fields = data.model_dump(exclude={"ingredients"}, exclude_none=True)
    dish = Dish(**fields)
    dish.recipe = [
        DishIngredient(ingredient_id=line.ingredient_id, quantity=line.quantity)
        for line in data.ingredients
    ]
    db.add(dish)
    db.commit()
    return get_dish(db, dish.id)


def update_dish(db: Session, dish_id: int, data: DishUpdate) -> DishOut:
    dish = _load_dish(db, dish_id)
    fields = data.model_dump(exclude={"ingredients"}, exclude_unset=True)
    for required in ("category_id", "name_ru", "base_price", "shelf_life_hours"):
        if required in fields and fields[required] is None:
            raise ValidationError("field_required", f"Поле {required} обязательно")
    if "category_id" in fields:
        _check_category(db, fields["category_id"])
    for key, value in fields.items():
        setattr(dish, key, value)
    if data.ingredients is not None:
        _check_recipe(db, data.ingredients)
        dish.recipe.clear()
        db.flush()
        dish.recipe.extend(
            DishIngredient(ingredient_id=line.ingredient_id, quantity=line.quantity)
            for line in data.ingredients
        )
    db.commit()
    return get_dish(db, dish.id)


# ---- ingredients ----------------------------------------------------------


def _ingredient_out(i: Ingredient) -> IngredientOut:
    return IngredientOut(
        id=i.id,
        name=i.name,
        unit=i.unit,
        allergens=[AllergenOut.model_validate(a) for a in i.allergens],
    )


def list_ingredients(db: Session) -> list[IngredientOut]:
    rows = db.scalars(
        select(Ingredient).options(joinedload(Ingredient.allergens)).order_by(Ingredient.name)
    ).unique()
    return [_ingredient_out(i) for i in rows]


def create_ingredient(db: Session, data: IngredientCreate) -> IngredientOut:
    name = data.name.strip().lower()
    if db.scalar(select(Ingredient.id).where(func.lower(Ingredient.name) == name)):
        raise ConflictError("ingredient_exists", "Такой ингредиент уже есть")
    allergen_ids = sorted(set(data.allergen_ids))
    if allergen_ids:
        known = set(db.scalars(select(Allergen.id).where(Allergen.id.in_(allergen_ids))))
        if known != set(allergen_ids):
            raise ValidationError("allergen_not_found", "Неизвестный аллерген")
    ingredient = Ingredient(name=name, unit=data.unit)
    db.add(ingredient)
    db.flush()
    for aid in allergen_ids:
        db.add(IngredientAllergen(ingredient_id=ingredient.id, allergen_id=aid))
    db.commit()
    db.refresh(ingredient)
    return _ingredient_out(ingredient)


# ---- menu of a day --------------------------------------------------------


def sold_portions(db: Session, menu_item_ids: list[int]) -> dict[int, int]:
    if not menu_item_ids:
        return {}
    rows = db.execute(
        select(OrderItem.menu_item_id, func.sum(OrderItem.quantity))
        .join(Order, Order.id == OrderItem.order_id)
        .where(OrderItem.menu_item_id.in_(menu_item_ids), Order.status != OrderStatus.cancelled)
        .group_by(OrderItem.menu_item_id)
    ).all()
    return {mid: int(total) for mid, total in rows}


def manager_menu(db: Session, canteen_id: int, day: date) -> ManagerMenu:
    items = list(
        db.scalars(
            select(MenuItem)
            .options(joinedload(MenuItem.dish).joinedload(Dish.category))
            .where(MenuItem.canteen_id == canteen_id, MenuItem.menu_date == day)
            .order_by(MenuItem.id)
        )
    )
    sold = sold_portions(db, [mi.id for mi in items])
    by_dish = allergy.dish_allergens(db, [mi.dish_id for mi in items])
    items.sort(key=lambda mi: (mi.dish.category.sort_order, mi.dish.name_ru))
    return ManagerMenu(
        canteen_id=canteen_id,
        date=day.isoformat(),
        items=[
            ManagerMenuItem(
                id=mi.id,
                dish_id=mi.dish_id,
                dish_name=mi.dish.name_ru,
                category_name=mi.dish.category.name,
                price=mi.price,
                planned_portions=mi.planned_portions,
                available_portions=mi.available_portions,
                sold_portions=sold.get(mi.id, 0),
                forecast_portions=mi.forecast_portions,
                forecast_model=mi.forecast_model,
                cooked_at=mi.cooked_at,
                allergens=[AllergenOut.model_validate(a) for a in by_dish.get(mi.dish_id, [])],
            )
            for mi in items
        ],
    )


def _set_planned(mi: MenuItem, planned: int) -> None:
    """Changing the plan keeps the number of portions already taken."""
    taken = mi.planned_portions - mi.available_portions
    if planned < taken:
        raise ConflictError(
            "planned_below_sold",
            f"Уже заказано {taken} порций, план не может быть меньше",
            {"taken": taken},
        )
    mi.planned_portions = planned
    mi.available_portions = planned - taken


def put_menu(db: Session, canteen_id: int, day: date, data: MenuPut) -> ManagerMenu:
    dish_ids = [i.dish_id for i in data.items]
    if len(dish_ids) != len(set(dish_ids)):
        raise ValidationError("duplicate_dish", "Блюдо указано дважды")
    if dish_ids:
        known = set(db.scalars(select(Dish.id).where(Dish.id.in_(dish_ids))))
        if known != set(dish_ids):
            raise ValidationError("dish_not_found", "Блюдо не найдено")
    existing = {
        mi.dish_id: mi
        for mi in db.scalars(
            select(MenuItem)
            .where(MenuItem.canteen_id == canteen_id, MenuItem.menu_date == day)
            .with_for_update()
        )
    }
    for item in data.items:
        mi = existing.pop(item.dish_id, None)
        if mi is None:
            db.add(
                MenuItem(
                    canteen_id=canteen_id,
                    dish_id=item.dish_id,
                    menu_date=day,
                    price=item.price,
                    planned_portions=item.planned_portions,
                    available_portions=item.planned_portions,
                )
            )
        else:
            mi.price = item.price
            _set_planned(mi, item.planned_portions)
    # Remaining items were removed from the menu; keep the ones that already have orders.
    removed_ids = [mi.id for mi in existing.values()]
    used = set(
        db.scalars(select(OrderItem.menu_item_id).where(OrderItem.menu_item_id.in_(removed_ids)))
    )
    for mi in existing.values():
        if mi.id in used:
            raise ConflictError(
                "menu_item_has_orders",
                "Блюдо уже заказывали, его нельзя убрать из меню",
                {"menu_item_id": mi.id},
            )
        db.delete(mi)
    db.commit()
    return manager_menu(db, canteen_id, day)


def patch_menu_item(db: Session, canteen_id: int, item_id: int, data: MenuItemPatch) -> MenuItem:
    mi = db.scalar(
        select(MenuItem)
        .where(MenuItem.id == item_id, MenuItem.canteen_id == canteen_id)
        .with_for_update()
    )
    if mi is None:
        raise NotFoundError("menu_item", "Позиция меню не найдена")
    if data.price is not None:
        mi.price = data.price
    if data.planned_portions is not None:
        _set_planned(mi, data.planned_portions)
    if data.available_portions is not None:
        if data.available_portions > mi.planned_portions:
            raise ValidationError("available_above_planned", "Остаток не может быть больше плана")
        mi.available_portions = data.available_portions
    db.commit()
    return mi
