from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User, UserRole
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
