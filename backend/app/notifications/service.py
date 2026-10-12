"""Notifications (SPEC 7.11): a row in the in-app feed, a live event, and optionally a Telegram
message and a Web Push. External deliveries are queued in Redis after commit and sent by the
bot and the worker, so a slow Telegram never holds up an order."""

from datetime import timedelta

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import NotFoundError
from app.i18n.messages import render
from app.models import (
    Notification,
    NotificationChannel,
    Order,
    OrderStatus,
    PickupSlot,
    PushSubscription,
    User,
)
from app.utils import time as clock
from app.ws import events

TELEGRAM_QUEUE = "outbox:telegram"
PUSH_QUEUE = "outbox:push"
# Advertising: the user can switch it off. Service messages always go out.
MARKETING = frozenset({"leftover_discount"})


def notify(
    db: Session,
    user: User,
    kind: str,
    *,
    order_id: int | None = None,
    promotion_id: int | None = None,
    url: str | None = None,
    **params: object,
) -> Notification | None:
    """Within the caller's transaction. One notification per order and kind (no duplicates)."""
    if kind in MARKETING and user.marketing_opt_out:
        return None
    message = render(kind, user.preferred_language, **params)
    stmt = insert(Notification).values(
        user_id=user.id,
        order_id=order_id,
        promotion_id=promotion_id,
        channel=NotificationChannel.in_app,
        kind=kind,
        title=message.title,
        body=message.body,
        sent_at=clock.now_utc(),
    )
    if order_id is not None:
        stmt = stmt.on_conflict_do_nothing(
            index_elements=["order_id", "kind"],
            index_where=Notification.order_id.is_not(None) & Notification.kind.is_not(None),
        )
    new_id = db.execute(stmt.returning(Notification.id)).scalar()
    if new_id is None:
        return None
    note = db.get(Notification, new_id)
    assert note is not None
    link = url or (f"/orders/{order_id}" if order_id else "/notifications")
    events.emit(
        db,
        events.notification_channel(user.id),
        "notification.new",
        {"id": note.id, "kind": kind, "title": note.title, "body": note.body, "url": link},
    )
    settings = get_settings()
    if user.telegram_chat_id and settings.telegram_bot_token:
        events.enqueue(
            db,
            TELEGRAM_QUEUE,
            {"chat_id": user.telegram_chat_id, "text": f"{note.title}\n{note.body}"},
        )
    if settings.vapid_private_key and db.scalar(
        select(func.count(PushSubscription.id)).where(PushSubscription.user_id == user.id)
    ):
        events.enqueue(
            db,
            PUSH_QUEUE,
            {"user_id": user.id, "title": note.title, "body": note.body, "url": link},
        )
    return note


def _slot(order: Order) -> str:
    return order.pickup_slot.starts_at.strftime("%H:%M") if order.pickup_slot else ""


def on_status_change(db: Session, order: Order) -> None:
    """Service notifications for the customer of an order whose status just changed."""
    if order.user_id is None:
        return
    user = db.get(User, order.user_id)
    if user is None:
        return
    common = {"order_id": order.id, "number": order.order_number}
    if order.status == OrderStatus.paid:
        notify(db, user, "order_paid", slot=_slot(order), **common)
    elif order.status == OrderStatus.ready:
        notify(db, user, "order_ready", shelf=order.pickup_shelf or "—", **common)
    elif order.status == OrderStatus.cancelled:
        notify(db, user, "order_cancelled", **common)


REMINDER_MINUTES = 5


def slot_reminders(db: Session) -> int:
    """Worker, every minute: a reminder 5 minutes before the slot of an order not yet picked up.
    Idempotent: the unique (order_id, kind) index keeps it to one per order."""
    tz = get_settings().tz
    now = clock.now_utc()
    slot_start = func.timezone(tz, PickupSlot.slot_date + PickupSlot.starts_at)
    rows = db.execute(
        select(Order, User)
        .join(PickupSlot, PickupSlot.id == Order.pickup_slot_id)
        .join(User, User.id == Order.user_id)
        .outerjoin(
            Notification,
            (Notification.order_id == Order.id) & (Notification.kind == "slot_reminder"),
        )
        .where(
            Order.status.in_([OrderStatus.paid, OrderStatus.cooking, OrderStatus.ready]),
            slot_start > now,
            slot_start <= now + timedelta(minutes=REMINDER_MINUTES),
            Notification.id.is_(None),
        )
        .order_by(Order.id)
    ).all()
    sent = 0
    for order, user in rows:
        if notify(
            db,
            user,
            "slot_reminder",
            order_id=order.id,
            number=order.order_number,
            slot=_slot(order),
        ):
            sent += 1
    db.commit()
    return sent


def list_for(db: Session, user: User, limit: int = 50) -> tuple[list[Notification], int]:
    items = db.scalars(
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.sent_at.desc(), Notification.id.desc())
        .limit(limit)
    ).all()
    unread = db.scalar(
        select(func.count(Notification.id)).where(
            Notification.user_id == user.id, Notification.read_at.is_(None)
        )
    )
    return list(items), unread or 0


def mark_read(db: Session, user: User, notification_id: int) -> Notification:
    note = db.get(Notification, notification_id)
    if note is None or note.user_id != user.id:
        raise NotFoundError("notification", "Уведомление не найдено")
    if note.read_at is None:
        note.read_at = clock.now_utc()
        db.commit()
    return note


def mark_all_read(db: Session, user: User) -> int:
    result = db.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.read_at.is_(None))
        .values(read_at=clock.now_utc())
    )
    db.commit()
    return result.rowcount
