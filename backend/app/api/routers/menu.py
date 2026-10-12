from datetime import date

from fastapi import APIRouter

from app.api.deps import DB
from app.schemas.menu import DishDetail, MenuResponse
from app.security import OptionalUser
from app.services import menu as menu_service

router = APIRouter(tags=["menu"])


@router.get("/canteens/{canteen_id}/menu", response_model=MenuResponse)
def canteen_menu(
    canteen_id: int, db: DB, user: OptionalUser, date: date | None = None
) -> MenuResponse:
    """Menu of the day. For a signed-in user each dish has `unsafe_for_me` / `warning_for_me`."""
    return menu_service.get_menu(db, canteen_id, date, user)


@router.get("/dishes/{dish_id}", response_model=DishDetail)
def dish_card(dish_id: int, db: DB, user: OptionalUser) -> DishDetail:
    return menu_service.get_dish(db, dish_id, user)
