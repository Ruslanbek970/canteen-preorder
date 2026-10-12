from datetime import date

from fastapi import APIRouter

from app.api.deps import DB, KitchenStaff, staff_canteen
from app.schemas.kitchen import (
    CloseDayResult,
    KitchenBoard,
    KitchenOrder,
    Label,
    PrepSummary,
    SlotStartResult,
    StatusChange,
    WasteIn,
    WasteOut,
)
from app.services import kitchen

router = APIRouter(prefix="/kitchen", tags=["kitchen"])


@router.get("/board", response_model=KitchenBoard)
def board(user: KitchenStaff, db: DB, date: date | None = None) -> KitchenBoard:
    """Today's paid / cooking / ready orders grouped by slot."""
    return kitchen.board(db, staff_canteen(user, db), date)


@router.get("/prep-summary", response_model=PrepSummary)
def prep_summary(user: KitchenStaff, db: DB) -> PrepSummary:
    return kitchen.prep_summary(db, staff_canteen(user, db))


@router.post("/orders/{order_id}/status", response_model=KitchenOrder)
def set_status(order_id: int, data: StatusChange, user: KitchenStaff, db: DB) -> KitchenOrder:
    return kitchen.set_status(db, user, staff_canteen(user, db), order_id, data.status)


@router.post("/slots/{slot_id}/start", response_model=SlotStartResult)
def start_slot(slot_id: int, user: KitchenStaff, db: DB) -> SlotStartResult:
    return kitchen.start_slot(db, user, staff_canteen(user, db), slot_id)


@router.get("/orders/{order_id}/label", response_model=Label)
def label(order_id: int, user: KitchenStaff, db: DB) -> Label:
    return kitchen.label(db, staff_canteen(user, db), order_id)


@router.post("/close-day", response_model=CloseDayResult)
def close_day(user: KitchenStaff, db: DB) -> CloseDayResult:
    return kitchen.close_day(db, user, staff_canteen(user, db))


@router.get("/waste", response_model=list[WasteOut])
def waste_list(user: KitchenStaff, db: DB) -> list[WasteOut]:
    return kitchen.waste_list(db, staff_canteen(user, db))


@router.post("/waste", response_model=WasteOut, status_code=201)
def record_waste(data: WasteIn, user: KitchenStaff, db: DB) -> WasteOut:
    return kitchen.record_waste(db, user, staff_canteen(user, db), data)
