from datetime import date

from fastapi import APIRouter, Response, status

from app.api.deps import DB, ManagedCanteen, ManagerOrAdmin
from app.schemas.catalog import (
    DishCreate,
    DishOut,
    DishUpdate,
    IngredientCreate,
    IngredientOut,
    ManagerMenu,
    MenuItemPatch,
    MenuPut,
)
from app.services import catalog

router = APIRouter(prefix="/manager", tags=["manager: catalog"])


@router.get("/dishes", response_model=list[DishOut])
def list_dishes(_: ManagerOrAdmin, db: DB) -> list[DishOut]:
    return catalog.list_dishes(db)


@router.get("/dishes/{dish_id}", response_model=DishOut)
def get_dish(dish_id: int, _: ManagerOrAdmin, db: DB) -> DishOut:
    return catalog.get_dish(db, dish_id)


@router.post("/dishes", response_model=DishOut, status_code=201)
def create_dish(data: DishCreate, _: ManagerOrAdmin, db: DB) -> DishOut:
    return catalog.create_dish(db, data)


@router.patch("/dishes/{dish_id}", response_model=DishOut)
def update_dish(dish_id: int, data: DishUpdate, _: ManagerOrAdmin, db: DB) -> DishOut:
    return catalog.update_dish(db, dish_id, data)


@router.delete("/dishes/{dish_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dish(dish_id: int, _: ManagerOrAdmin, db: DB) -> Response:
    catalog.delete_dish(db, dish_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/ingredients", response_model=list[IngredientOut])
def list_ingredients(_: ManagerOrAdmin, db: DB) -> list[IngredientOut]:
    return catalog.list_ingredients(db)


@router.post("/ingredients", response_model=IngredientOut, status_code=201)
def create_ingredient(data: IngredientCreate, _: ManagerOrAdmin, db: DB) -> IngredientOut:
    return catalog.create_ingredient(db, data)


@router.delete("/ingredients/{ingredient_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ingredient(ingredient_id: int, _: ManagerOrAdmin, db: DB) -> Response:
    catalog.delete_ingredient(db, ingredient_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/menu", response_model=ManagerMenu)
def get_menu(date: date, canteen_id: ManagedCanteen, db: DB) -> ManagerMenu:
    return catalog.manager_menu(db, canteen_id, date)


@router.put("/menu", response_model=ManagerMenu)
def put_menu(date: date, data: MenuPut, canteen_id: ManagedCanteen, db: DB) -> ManagerMenu:
    return catalog.put_menu(db, canteen_id, date, data)


@router.patch("/menu-items/{item_id}", response_model=ManagerMenu)
def patch_menu_item(
    item_id: int, data: MenuItemPatch, canteen_id: ManagedCanteen, db: DB
) -> ManagerMenu:
    item = catalog.patch_menu_item(db, canteen_id, item_id, data)
    return catalog.manager_menu(db, canteen_id, item.menu_date)


@router.delete("/menu-items/{item_id}", response_model=ManagerMenu)
def delete_menu_item(item_id: int, canteen_id: ManagedCanteen, db: DB) -> ManagerMenu:
    day = catalog.delete_menu_item(db, canteen_id, item_id)
    return catalog.manager_menu(db, canteen_id, day)
