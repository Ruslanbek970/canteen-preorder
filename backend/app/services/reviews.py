"""Dish reviews (SPEC 7.12): after pickup, within 48 hours, once per order item."""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import ConflictError, NotFoundError
from app.models import DishReview, Order, OrderItem, OrderStatus, User
from app.schemas.reviews import ReviewCreated, ReviewIn
from app.utils import time as clock

REVIEW_WINDOW = timedelta(hours=48)


def review_until(order: Order) -> datetime | None:
    """When the review window closes; None if the order cannot be reviewed now."""
    if order.status != OrderStatus.picked_up or order.picked_up_at is None:
        return None
    until = order.picked_up_at + REVIEW_WINDOW
    return until if clock.now_utc() < until else None


def ratings_for_items(db: Session, item_ids: list[int]) -> dict[int, int]:
    if not item_ids:
        return {}
    rows = db.execute(
        select(DishReview.order_item_id, DishReview.rating).where(
            DishReview.order_item_id.in_(item_ids)
        )
    ).all()
    return dict(rows)


def create_review(db: Session, user: User, order_item_id: int, data: ReviewIn) -> ReviewCreated:
    item = db.get(OrderItem, order_item_id)
    order = db.get(Order, item.order_id) if item else None
    if item is None or order is None or order.user_id != user.id:
        raise NotFoundError("order_item", "Позиция заказа не найдена")
    if order.status != OrderStatus.picked_up:
        raise ConflictError("order_not_picked_up", "Оценить можно только полученный заказ")
    if review_until(order) is None:
        raise ConflictError("review_window_closed", "Оценить можно в течение 48 часов")
    comment = (data.comment or "").strip() or None
    review = DishReview(order_item_id=item.id, rating=data.rating, comment=comment)
    db.add(review)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError("already_reviewed", "Эту позицию вы уже оценили") from None
    db.refresh(review)
    return ReviewCreated.model_validate(review, from_attributes=True)
