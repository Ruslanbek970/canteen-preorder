from fastapi import APIRouter

from app.api.deps import DB
from app.config import get_settings
from app.errors import NotFoundError
from app.notifications import service
from app.schemas.notifications import (
    NotificationList,
    NotificationOut,
    PushPublicKey,
    ReadAllResult,
)
from app.security import CurrentUser

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationList)
def my_notifications(user: CurrentUser, db: DB, limit: int = 50) -> NotificationList:
    items, unread = service.list_for(db, user, max(1, min(limit, 100)))
    return NotificationList(items=[NotificationOut.model_validate(n) for n in items], unread=unread)


@router.get("/push-key", response_model=PushPublicKey)
def push_key(user: CurrentUser) -> PushPublicKey:
    """The VAPID public key for the browser; 404 while Web Push is not configured."""
    key = get_settings().vapid_public_key
    if not key:
        raise NotFoundError("push_disabled", "Web Push не настроен")
    return PushPublicKey(public_key=key)


@router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_read(notification_id: int, user: CurrentUser, db: DB) -> NotificationOut:
    return NotificationOut.model_validate(service.mark_read(db, user, notification_id))


@router.post("/read-all", response_model=ReadAllResult)
def mark_all_read(user: CurrentUser, db: DB) -> ReadAllResult:
    return ReadAllResult(marked=service.mark_all_read(db, user))
