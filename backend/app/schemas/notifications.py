from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str | None
    title: str
    body: str
    order_id: int | None
    promotion_id: int | None
    sent_at: datetime
    read_at: datetime | None


class NotificationList(BaseModel):
    items: list[NotificationOut]
    unread: int


class ReadAllResult(BaseModel):
    marked: int


class PushKeys(BaseModel):
    p256dh: str = Field(max_length=255)
    auth: str = Field(max_length=255)


class PushSubscriptionIn(BaseModel):
    endpoint: str = Field(max_length=2000, pattern=r"^https://")
    keys: PushKeys


class PushUnsubscribe(BaseModel):
    endpoint: str


class PushPublicKey(BaseModel):
    public_key: str


class TelegramLinkCode(BaseModel):
    code: str
    expires_in: int
    bot_username: str | None
    deep_link: str | None
