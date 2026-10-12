from datetime import date

from fastapi import APIRouter

from app.api.deps import DB, ManagedCanteen, ManagerOrAdmin
from app.models import Canteen
from app.schemas.slots import ManagerSlotsResponse, SlotOut, SlotPatch, SlotsResponse
from app.security import CurrentUser
from app.services import menu as menu_service
from app.services import slots as slot_service
from app.utils import time as clock

router = APIRouter(tags=["slots"])


@router.get("/canteens/{canteen_id}/slots", response_model=SlotsResponse)
def canteen_slots(
    canteen_id: int, db: DB, user: CurrentUser, date: date | None = None
) -> SlotsResponse:
    """Slots that suit the user (SPEC 7.4): no lesson overlap, after the cutoff, not full."""
    canteen = menu_service.get_canteen(db, canteen_id)
    return slot_service.slots_for_user(db, canteen, date or clock.today_local(), user)


@router.get("/manager/slots", response_model=ManagerSlotsResponse)
def manager_slots(
    _: ManagerOrAdmin, canteen_id: ManagedCanteen, db: DB, date: date | None = None
) -> ManagerSlotsResponse:
    day = date or clock.today_local()
    return ManagerSlotsResponse(
        canteen_id=canteen_id, date=day, slots=slot_service.manager_slots(db, canteen_id, day)
    )


@router.post("/manager/slots/generate", response_model=ManagerSlotsResponse)
def generate_slots(
    _: ManagerOrAdmin, canteen_id: ManagedCanteen, db: DB, date: date | None = None
) -> ManagerSlotsResponse:
    """The worker does this every day at 05:00; the button is for a missed day."""
    day = date or clock.today_local()
    canteen = db.get(Canteen, canteen_id)
    assert canteen is not None
    slot_service.generate_slots(db, canteen, day)
    return ManagerSlotsResponse(
        canteen_id=canteen_id, date=day, slots=slot_service.manager_slots(db, canteen_id, day)
    )


@router.patch("/manager/slots/{slot_id}", response_model=SlotOut)
def patch_slot(
    slot_id: int, data: SlotPatch, _: ManagerOrAdmin, canteen_id: ManagedCanteen, db: DB
) -> SlotOut:
    return slot_service.to_out(slot_service.patch_slot(db, canteen_id, slot_id, data))
