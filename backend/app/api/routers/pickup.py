from fastapi import APIRouter

from app.api.deps import DB, PickupStaff, staff_canteen
from app.schemas.pickup import PickupOrder, PosReceipt, PosSale
from app.services import pickup

router = APIRouter(tags=["pickup"])


@router.get("/pickup/scan/{qr_token}", response_model=PickupOrder)
def scan(qr_token: str, user: PickupStaff, db: DB) -> PickupOrder:
    return pickup.by_qr(db, staff_canteen(user, db), qr_token)


@router.get("/pickup/by-number/{order_number}", response_model=PickupOrder)
def by_number(order_number: str, user: PickupStaff, db: DB) -> PickupOrder:
    """Today's order by its number; `A7`, `a-007` and `7` all find `A-007`."""
    return pickup.by_number(db, staff_canteen(user, db), order_number)


@router.post("/pickup/orders/{order_id}/confirm", response_model=PickupOrder)
def confirm(order_id: int, user: PickupStaff, db: DB) -> PickupOrder:
    return pickup.confirm(db, user, staff_canteen(user, db), order_id)


@router.post("/pos/sales", response_model=PosReceipt, status_code=201)
def pos_sale(data: PosSale, user: PickupStaff, db: DB) -> PosReceipt:
    return pickup.pos_sale(db, user, staff_canteen(user, db), data)
