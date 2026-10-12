from fastapi import APIRouter, status

from app.api.deps import DB, ManagedCanteen, ManagerOrAdmin
from app.models import PromotionStatus
from app.schemas.promotions import OffPeakCreate, PromotionOut
from app.services import promotions

router = APIRouter(prefix="/manager/promotions", tags=["promotions"])


@router.get("", response_model=list[PromotionOut])
def list_promotions(
    canteen_id: ManagedCanteen, db: DB, status: PromotionStatus | None = None
) -> list[PromotionOut]:
    return promotions.list_promotions(db, canteen_id, status)


@router.post("", response_model=PromotionOut, status_code=status.HTTP_201_CREATED)
def create_off_peak(
    data: OffPeakCreate, user: ManagerOrAdmin, canteen_id: ManagedCanteen, db: DB
) -> PromotionOut:
    return promotions.create_off_peak(db, user, canteen_id, data)


@router.post("/{promotion_id}/approve", response_model=PromotionOut)
def approve(
    promotion_id: int, user: ManagerOrAdmin, canteen_id: ManagedCanteen, db: DB
) -> PromotionOut:
    return promotions.approve(db, user, canteen_id, promotion_id)


@router.post("/{promotion_id}/reject", response_model=PromotionOut)
def reject(
    promotion_id: int, user: ManagerOrAdmin, canteen_id: ManagedCanteen, db: DB
) -> PromotionOut:
    return promotions.reject(db, user, canteen_id, promotion_id)
