"""Loyalty points (SPEC 7.10): 1 point per 100 ₸ of a paid and picked-up order."""

from decimal import Decimal

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models import Order, User

TENGE_PER_POINT = Decimal(100)


def points_for(total: Decimal) -> int:
    return int(total // TENGE_PER_POINT)


def award(db: Session, order: Order) -> int:
    """Inside the pickup transaction; atomic, so parallel pickups never lose points."""
    points = points_for(order.total)
    if order.user_id is None or points <= 0:
        return 0
    db.execute(
        update(User)
        .where(User.id == order.user_id)
        .values(loyalty_points=User.loyalty_points + points)
    )
    return points
