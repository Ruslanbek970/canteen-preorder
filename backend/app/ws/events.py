"""Realtime events (SPEC 8.11): queued on the DB session and published to Redis after commit,
so nobody hears about a change that was rolled back."""

import json
import logging
from typing import Any

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.redis_client import get_redis

log = logging.getLogger(__name__)

_KEY = "pending_events"


def user_channel(user_id: int) -> str:
    return f"ws:user:{user_id}"


def kitchen_channel(canteen_id: int) -> str:
    return f"ws:kitchen:{canteen_id}"


def emit(db: Session, channel: str, kind: str, data: dict[str, Any]) -> None:
    db.info.setdefault(_KEY, []).append((channel, {"type": kind, "data": data}))


def publish(channel: str, message: dict[str, Any]) -> None:
    try:
        get_redis().publish(channel, json.dumps(message, default=str))
    except Exception:  # pragma: no cover - realtime is best effort
        log.warning("could not publish %s", message.get("type"), exc_info=True)


@event.listens_for(Session, "after_commit")
def _flush_events(session: Session) -> None:
    for channel, message in session.info.pop(_KEY, []):
        publish(channel, message)


@event.listens_for(Session, "after_rollback")
def _drop_events(session: Session) -> None:
    session.info.pop(_KEY, None)


def order_event(db: Session, kind: str, order: Any) -> None:
    """The same small payload to the owner and to the canteen's kitchen screens."""
    data = {
        "order_id": order.id,
        "order_number": order.order_number,
        "status": order.status,
        "pickup_slot_id": order.pickup_slot_id,
        "pickup_shelf": order.pickup_shelf,
    }
    if order.user_id is not None:
        emit(db, user_channel(order.user_id), kind, data)
    emit(db, kitchen_channel(order.canteen_id), kind, data)
