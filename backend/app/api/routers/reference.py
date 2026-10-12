from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import DB
from app.errors import NotFoundError
from app.models import Allergen, Canteen, DishCategory, StudentGroup
from app.schemas.reference import AllergenOut, CanteenOut, CategoryOut, GroupOut

router = APIRouter(tags=["reference"])


@router.get("/canteens", response_model=list[CanteenOut])
def list_canteens(db: DB) -> list[Canteen]:
    return list(db.scalars(select(Canteen).where(Canteen.is_active).order_by(Canteen.id)))


@router.get("/canteens/by-slug/{slug}", response_model=CanteenOut)
def canteen_by_slug(slug: str, db: DB) -> Canteen:
    canteen = db.scalar(select(Canteen).where(Canteen.slug == slug, Canteen.is_active))
    if canteen is None:
        raise NotFoundError("canteen", "Столовая не найдена")
    return canteen


@router.get("/groups", response_model=list[GroupOut])
def list_groups(db: DB) -> list[StudentGroup]:
    return list(db.scalars(select(StudentGroup).order_by(StudentGroup.code)))


@router.get("/allergens", response_model=list[AllergenOut])
def list_allergens(db: DB) -> list[Allergen]:
    return list(db.scalars(select(Allergen).order_by(Allergen.id)))


@router.get("/dish-categories", response_model=list[CategoryOut])
def list_categories(db: DB) -> list[DishCategory]:
    return list(db.scalars(select(DishCategory).order_by(DishCategory.sort_order)))
