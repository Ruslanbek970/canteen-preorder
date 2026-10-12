from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import ForbiddenError, NotFoundError
from app.models import Canteen, User, UserRole
from app.security import require_roles

DB = Annotated[Session, Depends(get_db)]

Customer = Annotated[User, Depends(require_roles(UserRole.student, UserRole.teacher))]
KitchenStaff = Annotated[User, Depends(require_roles(UserRole.cook, UserRole.canteen_manager))]
PickupStaff = Annotated[User, Depends(require_roles(UserRole.cashier, UserRole.canteen_manager))]
Manager = Annotated[User, Depends(require_roles(UserRole.canteen_manager))]
ManagerOrAdmin = Annotated[User, Depends(require_roles(UserRole.canteen_manager, UserRole.admin))]
Admin = Annotated[User, Depends(require_roles(UserRole.admin))]


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def pagination(limit: int = 50, offset: int = 0) -> tuple[int, int]:
    return max(1, min(limit, 200)), max(0, offset)


Page = Annotated[tuple[int, int], Depends(pagination)]


def manager_canteen_id(user: ManagerOrAdmin, db: DB, canteen_id: int | None = None) -> int:
    """The canteen a manager works with: their own; an admin picks one (default: the first)."""
    if user.role == UserRole.canteen_manager:
        if canteen_id is not None and canteen_id != user.canteen_id:
            raise ForbiddenError("foreign_canteen", "Access to another canteen is not allowed")
        assert user.canteen_id is not None
        return user.canteen_id
    if canteen_id is None:
        canteen_id = db.scalar(select(Canteen.id).order_by(Canteen.id).limit(1))
        if canteen_id is None:
            raise NotFoundError("canteen", "No canteens yet")
    elif db.get(Canteen, canteen_id) is None:
        raise NotFoundError("canteen", "Столовая не найдена")
    return canteen_id


ManagedCanteen = Annotated[int, Depends(manager_canteen_id)]


def staff_canteen(user: User, db: Session, canteen_id: int | None = None) -> int:
    """Kitchen and pickup staff work with their own canteen (SPEC 6)."""
    if user.canteen_id is None:
        raise ForbiddenError("no_canteen", "User is not attached to a canteen")
    if canteen_id is not None and canteen_id != user.canteen_id:
        raise ForbiddenError("foreign_canteen", "Access to another canteen is not allowed")
    return user.canteen_id
