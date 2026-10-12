import uuid
from datetime import date, datetime, time
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampTZ, bigint_pk, created_at_col, int_pk
from app.models.enums import (
    OrderChannel,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
    PromotionStatus,
    PromotionType,
    order_channel,
    order_status,
    payment_method,
    payment_status,
    promotion_status,
    promotion_type,
)
from app.models.menu import MenuItem


class PickupSlot(Base):
    __tablename__ = "pickup_slots"
    __table_args__ = (
        sa.CheckConstraint("capacity > 0", name="capacity"),
        sa.CheckConstraint("booked_count >= 0", name="booked_count"),
        sa.CheckConstraint("starts_at < ends_at", name="times"),
        sa.CheckConstraint("booked_count <= capacity", name="booked_le_capacity"),
        sa.UniqueConstraint("canteen_id", "slot_date", "starts_at"),
        sa.Index("idx_slots_day", "canteen_id", "slot_date"),
    )

    id: Mapped[int] = int_pk()
    canteen_id: Mapped[int] = mapped_column(sa.ForeignKey("canteens.id"), nullable=False)
    slot_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    starts_at: Mapped[time] = mapped_column(sa.Time, nullable=False)
    ends_at: Mapped[time] = mapped_column(sa.Time, nullable=False)
    capacity: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)
    booked_count: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False, server_default="0")
    # Added by migration 3: the manager can close a slot (SPEC 7.4).
    is_closed: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.false())


class Promotion(Base):
    __tablename__ = "promotions"
    __table_args__ = (
        sa.CheckConstraint("discount_percent BETWEEN 1 AND 90", name="discount_percent"),
        sa.CheckConstraint("valid_from < valid_to", name="validity"),
        sa.CheckConstraint(
            "(type = 'leftover' AND menu_item_id IS NOT NULL) OR "
            "(type = 'off_peak' AND pickup_slot_id IS NOT NULL) OR "
            "(type = 'loyalty')",
            name="target",
        ),
    )

    id: Mapped[int] = int_pk()
    type: Mapped[PromotionType] = mapped_column(promotion_type, nullable=False)
    menu_item_id: Mapped[int | None] = mapped_column(sa.ForeignKey("menu_items.id"))
    pickup_slot_id: Mapped[int | None] = mapped_column(sa.ForeignKey("pickup_slots.id"))
    discount_percent: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)
    valid_from: Mapped[datetime] = mapped_column(TimestampTZ, nullable=False)
    valid_to: Mapped[datetime] = mapped_column(TimestampTZ, nullable=False)
    status: Mapped[PromotionStatus] = mapped_column(
        promotion_status, nullable=False, server_default=PromotionStatus.proposed.value
    )
    created_by_system: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.true()
    )
    approved_by: Mapped[int | None] = mapped_column(sa.ForeignKey("users.id"))
    created_at: Mapped[datetime] = created_at_col()

    menu_item: Mapped[MenuItem | None] = relationship()
    pickup_slot: Mapped[PickupSlot | None] = relationship()


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        sa.CheckConstraint("subtotal >= 0", name="subtotal"),
        sa.CheckConstraint("discount_total >= 0", name="discount_total"),
        sa.CheckConstraint("discount_total <= subtotal", name="discount_le_subtotal"),
        sa.CheckConstraint(
            "channel = 'cashier' OR (user_id IS NOT NULL AND pickup_slot_id IS NOT NULL)",
            name="channel_owner",
        ),
        sa.UniqueConstraint("canteen_id", "service_date", "order_number"),
        sa.Index("idx_orders_user", "user_id", sa.text("created_at DESC")),
        sa.Index("idx_orders_slot", "pickup_slot_id"),
        sa.Index(
            "idx_orders_kitchen_active",
            "canteen_id",
            "service_date",
            postgresql_where=sa.text("status IN ('paid', 'cooking', 'ready')"),
        ),
    )

    id: Mapped[int] = bigint_pk()
    order_number: Mapped[str] = mapped_column(sa.String(10), nullable=False)
    user_id: Mapped[int | None] = mapped_column(sa.ForeignKey("users.id"))
    canteen_id: Mapped[int] = mapped_column(sa.ForeignKey("canteens.id"), nullable=False)
    service_date: Mapped[date] = mapped_column(
        sa.Date, nullable=False, server_default=sa.text("CURRENT_DATE")
    )
    pickup_slot_id: Mapped[int | None] = mapped_column(sa.ForeignKey("pickup_slots.id"))
    channel: Mapped[OrderChannel] = mapped_column(order_channel, nullable=False)
    status: Mapped[OrderStatus] = mapped_column(
        order_status, nullable=False, server_default=OrderStatus.pending_payment.value
    )
    subtotal: Mapped[Decimal] = mapped_column(sa.Numeric(10, 2), nullable=False, server_default="0")
    discount_total: Mapped[Decimal] = mapped_column(
        sa.Numeric(10, 2), nullable=False, server_default="0"
    )
    total: Mapped[Decimal] = mapped_column(
        sa.Numeric(10, 2), sa.Computed("subtotal - discount_total", persisted=True)
    )
    qr_token: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        unique=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    allergy_warning_ack: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.false()
    )
    created_at: Mapped[datetime] = created_at_col()
    paid_at: Mapped[datetime | None] = mapped_column(TimestampTZ)
    ready_at: Mapped[datetime | None] = mapped_column(TimestampTZ)
    picked_up_at: Mapped[datetime | None] = mapped_column(TimestampTZ)
    # Added by migration 2 (SPEC 5.2)
    pickup_shelf: Mapped[int | None] = mapped_column(sa.SmallInteger)

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", order_by="OrderItem.id"
    )
    pickup_slot: Mapped[PickupSlot | None] = relationship()


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (
        sa.CheckConstraint("quantity BETWEEN 1 AND 10", name="quantity"),
        sa.CheckConstraint("unit_price >= 0", name="unit_price"),
        sa.CheckConstraint("discount_amount >= 0", name="discount_amount"),
        sa.UniqueConstraint("order_id", "menu_item_id"),
        sa.Index("idx_order_items_order", "order_id"),
        sa.Index("idx_order_items_menu", "menu_item_id"),
    )

    id: Mapped[int] = bigint_pk()
    order_id: Mapped[int] = mapped_column(
        sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    menu_item_id: Mapped[int] = mapped_column(sa.ForeignKey("menu_items.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(sa.Numeric(10, 2), nullable=False)
    promotion_id: Mapped[int | None] = mapped_column(sa.ForeignKey("promotions.id"))
    discount_amount: Mapped[Decimal] = mapped_column(
        sa.Numeric(10, 2), nullable=False, server_default="0"
    )

    order: Mapped[Order] = relationship(back_populates="items")
    menu_item: Mapped[MenuItem] = relationship()


class OrderStatusHistory(Base):
    __tablename__ = "order_status_history"
    __table_args__ = (sa.Index("idx_status_history_order", "order_id"),)

    id: Mapped[int] = bigint_pk()
    order_id: Mapped[int] = mapped_column(
        sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    from_status: Mapped[OrderStatus | None] = mapped_column(order_status)
    to_status: Mapped[OrderStatus] = mapped_column(order_status, nullable=False)
    changed_by: Mapped[int | None] = mapped_column(sa.ForeignKey("users.id"))
    changed_at: Mapped[datetime] = mapped_column(
        TimestampTZ, nullable=False, server_default=sa.func.now()
    )


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        sa.CheckConstraint("amount > 0", name="amount"),
        sa.Index("idx_payments_order", "order_id"),
    )

    id: Mapped[int] = bigint_pk()
    order_id: Mapped[int] = mapped_column(sa.ForeignKey("orders.id"), nullable=False)
    method: Mapped[PaymentMethod] = mapped_column(payment_method, nullable=False)
    amount: Mapped[Decimal] = mapped_column(sa.Numeric(10, 2), nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(
        payment_status, nullable=False, server_default=PaymentStatus.pending.value
    )
    provider_transaction_id: Mapped[str | None] = mapped_column(sa.String(100), unique=True)
    fiscal_receipt_number: Mapped[str | None] = mapped_column(sa.String(50))
    created_at: Mapped[datetime] = created_at_col()
    completed_at: Mapped[datetime | None] = mapped_column(TimestampTZ)
