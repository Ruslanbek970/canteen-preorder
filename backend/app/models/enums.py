"""PostgreSQL ENUM types from docs/schema.sql. Member names equal their values."""

from enum import StrEnum

import sqlalchemy as sa


class UserRole(StrEnum):
    student = "student"
    teacher = "teacher"
    cook = "cook"
    cashier = "cashier"
    canteen_manager = "canteen_manager"
    admin = "admin"


class OrderStatus(StrEnum):
    pending_payment = "pending_payment"
    paid = "paid"
    cooking = "cooking"
    ready = "ready"
    picked_up = "picked_up"
    cancelled = "cancelled"
    no_show = "no_show"


class OrderChannel(StrEnum):
    mobile_app = "mobile_app"
    web_qr = "web_qr"
    cashier = "cashier"


class PaymentMethod(StrEnum):
    kaspi_qr = "kaspi_qr"
    bank_card = "bank_card"
    cash = "cash"


class PaymentStatus(StrEnum):
    pending = "pending"
    succeeded = "succeeded"
    failed = "failed"
    refunded = "refunded"


class PromotionType(StrEnum):
    leftover = "leftover"
    off_peak = "off_peak"
    loyalty = "loyalty"


class PromotionStatus(StrEnum):
    proposed = "proposed"
    active = "active"
    rejected = "rejected"
    expired = "expired"


class NotificationChannel(StrEnum):
    in_app = "in_app"
    push = "push"
    telegram = "telegram"
    sms = "sms"


class AllergySeverity(StrEnum):
    mild = "mild"
    moderate = "moderate"
    severe = "severe"


class WasteReason(StrEnum):
    expired = "expired"
    uncollected_order = "uncollected_order"
    damaged = "damaged"
    other = "other"


def pg_enum(enum_cls: type[StrEnum], name: str) -> sa.Enum:
    return sa.Enum(enum_cls, name=name, values_callable=lambda e: [m.value for m in e])


user_role = pg_enum(UserRole, "user_role")
order_status = pg_enum(OrderStatus, "order_status")
order_channel = pg_enum(OrderChannel, "order_channel")
payment_method = pg_enum(PaymentMethod, "payment_method")
payment_status = pg_enum(PaymentStatus, "payment_status")
promotion_type = pg_enum(PromotionType, "promotion_type")
promotion_status = pg_enum(PromotionStatus, "promotion_status")
notification_channel = pg_enum(NotificationChannel, "notification_channel")
allergy_severity = pg_enum(AllergySeverity, "allergy_severity")
waste_reason = pg_enum(WasteReason, "waste_reason")
