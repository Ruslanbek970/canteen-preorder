from datetime import date, datetime
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampTZ, bigint_pk, created_at_col, int_pk
from app.models.enums import (
    NotificationChannel,
    WasteReason,
    notification_channel,
    waste_reason,
)


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        sa.Index(
            "idx_notifications_unread", "user_id", postgresql_where=sa.text("read_at IS NULL")
        ),
        sa.Index("idx_notifications_user_sent", "user_id", sa.text("sent_at DESC")),
        sa.Index(
            "uq_notifications_order_kind",
            "order_id",
            "kind",
            unique=True,
            postgresql_where=sa.text("order_id IS NOT NULL AND kind IS NOT NULL"),
        ),
    )

    id: Mapped[int] = bigint_pk()
    user_id: Mapped[int] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    order_id: Mapped[int | None] = mapped_column(sa.ForeignKey("orders.id"))
    promotion_id: Mapped[int | None] = mapped_column(sa.ForeignKey("promotions.id"))
    channel: Mapped[NotificationChannel] = mapped_column(notification_channel, nullable=False)
    kind: Mapped[str | None] = mapped_column(sa.String(30))
    title: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    body: Mapped[str] = mapped_column(sa.Text, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(
        TimestampTZ, nullable=False, server_default=sa.func.now()
    )
    read_at: Mapped[datetime | None] = mapped_column(TimestampTZ)


class DishReview(Base):
    __tablename__ = "dish_reviews"
    __table_args__ = (sa.CheckConstraint("rating BETWEEN 1 AND 5", name="rating"),)

    id: Mapped[int] = int_pk()
    order_item_id: Mapped[int] = mapped_column(
        sa.ForeignKey("order_items.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    rating: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)
    comment: Mapped[str | None] = mapped_column(sa.Text)
    created_at: Mapped[datetime] = created_at_col()


class WasteRecord(Base):
    __tablename__ = "waste_records"
    __table_args__ = (
        sa.CheckConstraint("portions > 0", name="portions"),
        sa.CheckConstraint(
            "reason <> 'uncollected_order' OR order_id IS NOT NULL", name="uncollected_order"
        ),
        sa.Index("idx_waste_menu_item", "menu_item_id"),
    )

    id: Mapped[int] = int_pk()
    menu_item_id: Mapped[int] = mapped_column(sa.ForeignKey("menu_items.id"), nullable=False)
    portions: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)
    reason: Mapped[WasteReason] = mapped_column(waste_reason, nullable=False)
    order_id: Mapped[int | None] = mapped_column(sa.ForeignKey("orders.id"))
    recorded_by: Mapped[int | None] = mapped_column(sa.ForeignKey("users.id"))
    recorded_at: Mapped[datetime] = mapped_column(
        TimestampTZ, nullable=False, server_default=sa.func.now()
    )


# ---- Tables added by migration 2 (SPEC 5.2) ----------------------------


class DailyCounter(Base):
    __tablename__ = "daily_counters"

    canteen_id: Mapped[int] = mapped_column(sa.ForeignKey("canteens.id"), primary_key=True)
    service_date: Mapped[date] = mapped_column(sa.Date, primary_key=True)
    prefix: Mapped[str] = mapped_column(sa.String(2), primary_key=True)
    last_value: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="0")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    __table_args__ = (sa.Index("idx_refresh_tokens_user", "user_id"),)

    id: Mapped[int] = bigint_pk()
    user_id: Mapped[int] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(sa.String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(TimestampTZ, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(TimestampTZ)
    created_at: Mapped[datetime] = created_at_col()


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id: Mapped[int] = bigint_pk()
    user_id: Mapped[int] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    endpoint: Mapped[str] = mapped_column(sa.Text, nullable=False, unique=True)
    p256dh: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    auth: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    created_at: Mapped[datetime] = created_at_col()


class ForecastRun(Base):
    __tablename__ = "forecast_runs"

    id: Mapped[int] = int_pk()
    run_at: Mapped[datetime] = mapped_column(
        TimestampTZ, nullable=False, server_default=sa.func.now()
    )
    target_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    model: Mapped[str] = mapped_column(sa.String(30), nullable=False)
    mae: Mapped[Decimal | None] = mapped_column(sa.Numeric(10, 3))
    mape: Mapped[Decimal | None] = mapped_column(sa.Numeric(10, 3))
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
