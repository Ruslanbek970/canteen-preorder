"""Web Push (SPEC 7.11): browser subscriptions and delivery of queued notifications."""

import json
import logging

from pywebpush import WebPushException, webpush
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import PushSubscription, User
from app.notifications.service import PUSH_QUEUE
from app.redis_client import get_redis
from app.schemas.notifications import PushSubscriptionIn

log = logging.getLogger(__name__)
GONE = {404, 410}


def save_subscription(db: Session, user: User, data: PushSubscriptionIn) -> None:
    """Upsert by endpoint: a browser re-subscribing (or a new user on it) takes it over."""
    existing = db.scalar(select(PushSubscription).where(PushSubscription.endpoint == data.endpoint))
    if existing is None:
        db.add(
            PushSubscription(
                user_id=user.id,
                endpoint=data.endpoint,
                p256dh=data.keys.p256dh,
                auth=data.keys.auth,
            )
        )
    else:
        existing.user_id = user.id
        existing.p256dh = data.keys.p256dh
        existing.auth = data.keys.auth
    db.commit()


def delete_subscription(db: Session, user: User, endpoint: str) -> None:
    db.execute(
        delete(PushSubscription).where(
            PushSubscription.user_id == user.id, PushSubscription.endpoint == endpoint
        )
    )
    db.commit()


def send(subscription: PushSubscription, payload: dict) -> bool:
    """Raises WebPushException on failure; the caller drops subscriptions that are gone."""
    settings = get_settings()
    webpush(
        subscription_info={
            "endpoint": subscription.endpoint,
            "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
        },
        data=json.dumps(payload, ensure_ascii=False),
        vapid_private_key=settings.vapid_private_key,
        vapid_claims={"sub": settings.vapid_subject},
        timeout=10,
    )
    return True


def deliver_queued(db: Session, batch: int = 200) -> int:
    """Worker, every 15 seconds: send what `notify` queued. Returns the number of pushes sent."""
    if not get_settings().vapid_private_key:
        return 0
    redis = get_redis()
    raw = redis.lpop(PUSH_QUEUE, batch) or []
    sent = 0
    for item in raw:
        payload = json.loads(item)
        subs = db.scalars(
            select(PushSubscription).where(PushSubscription.user_id == payload["user_id"])
        ).all()
        for sub in subs:
            try:
                sent += send(sub, {k: payload[k] for k in ("title", "body", "url")})
            except WebPushException as exc:
                status = exc.response.status_code if exc.response is not None else None
                if status in GONE:
                    db.delete(sub)
                else:
                    log.warning("web push failed (%s) for user %s", status, payload["user_id"])
            except Exception:
                log.warning("web push failed for user %s", payload["user_id"], exc_info=True)
    db.commit()
    return sent
