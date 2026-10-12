"""Payments through a PaymentProvider (SPEC 7.7). Only the mock provider exists."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import ConflictError, NotFoundError
from app.models import Canteen, Order, OrderStatus, Payment, PaymentMethod, PaymentStatus, User
from app.payments import get_provider
from app.schemas.payments import PaymentOut
from app.services.order_status import Actor, change_status
from app.utils import time as clock
from app.ws import events


def create_pending(db: Session, order: Order, method: PaymentMethod = PaymentMethod.kaspi_qr):
    amount = order.subtotal - order.discount_total
    if amount <= 0:
        return None
    payment = Payment(order_id=order.id, method=method, amount=amount)
    db.add(payment)
    db.flush()
    return payment


def payment_url(payment: Payment) -> str:
    return get_provider().create_payment(payment).url


def latest_pending(db: Session, order_id: int) -> Payment | None:
    return db.scalar(
        select(Payment)
        .where(Payment.order_id == order_id, Payment.status == PaymentStatus.pending)
        .order_by(Payment.id.desc())
        .limit(1)
    )


def to_out(db: Session, payment: Payment, order: Order) -> PaymentOut:
    canteen = db.get(Canteen, order.canteen_id)
    return PaymentOut(
        id=payment.id,
        order_id=order.id,
        order_number=order.order_number,
        canteen_name=canteen.name if canteen else "",
        method=payment.method,
        amount=payment.amount,
        status=payment.status,
        url=payment_url(payment) if payment.status == PaymentStatus.pending else None,
        fiscal_receipt_number=payment.fiscal_receipt_number,
    )


def _owned_payment(db: Session, user: User, payment_id: int, lock: bool = False):
    stmt = (
        select(Payment, Order)
        .join(Order, Order.id == Payment.order_id)
        .where(Payment.id == payment_id)
    )
    if lock:
        stmt = stmt.with_for_update(of=Payment)
    row = db.execute(stmt).first()
    if row is None or row.Order.user_id != user.id:
        raise NotFoundError("payment", "Платёж не найден")
    return row.Payment, row.Order


def get_payment(db: Session, user: User, payment_id: int) -> PaymentOut:
    payment, order = _owned_payment(db, user, payment_id)
    return to_out(db, payment, order)


def start_payment(db: Session, user: User, order_id: int) -> PaymentOut:
    """«Оплатить» again after a failed attempt: reuses the pending payment or opens a new one."""
    order = db.scalar(select(Order).where(Order.id == order_id).with_for_update())
    if order is None or order.user_id != user.id:
        raise NotFoundError("order", "Заказ не найден")
    if order.status != OrderStatus.pending_payment:
        raise ConflictError("order_not_payable", "Этот заказ уже нельзя оплатить")
    payment = latest_pending(db, order.id) or create_pending(db, order)
    if payment is None:
        raise ConflictError("nothing_to_pay", "Заказ бесплатный")
    db.commit()
    return to_out(db, payment, order)


def settle(
    db: Session, payment_id: int, succeeded: bool, transaction_id: str | None = None
) -> tuple[Payment, Order]:
    """Applies a provider's answer. Idempotent for a repeated success webhook."""
    payment = db.scalar(select(Payment).where(Payment.id == payment_id).with_for_update())
    if payment is None:
        raise NotFoundError("payment", "Платёж не найден")
    order = db.scalar(select(Order).where(Order.id == payment.order_id).with_for_update())
    assert order is not None
    if payment.status == PaymentStatus.succeeded and succeeded:
        db.commit()
        return payment, order
    if payment.status != PaymentStatus.pending:
        raise ConflictError("payment_not_pending", "Платёж уже обработан")
    now = clock.now_utc()
    if succeeded and order.status != OrderStatus.pending_payment:
        # Paid too late (the order expired): the money goes back at once.
        payment.status = PaymentStatus.refunded
        payment.completed_at = now
        db.commit()
        raise ConflictError("order_not_payable", "Время на оплату вышло, заказ отменён")
    if succeeded:
        provider = get_provider()
        payment.status = PaymentStatus.succeeded
        payment.provider_transaction_id = transaction_id
        payment.fiscal_receipt_number = provider.fiscal_receipt_number(payment)
        payment.completed_at = now
        change_status(db, order, OrderStatus.paid, Actor.system)
    else:
        payment.status = PaymentStatus.failed
        payment.completed_at = now
        events.order_event(db, "payment.failed", order)
    db.commit()
    return payment, order


def mock_result(db: Session, user: User, payment_id: int, succeeded: bool) -> PaymentOut:
    """«Оплатить» / «Отказ» on the mock page: the owner imitates the provider's webhook."""
    _owned_payment(db, user, payment_id)
    db.rollback()
    result = get_provider("mock").handle_webhook({"payment_id": payment_id, "succeeded": succeeded})
    payment, order = settle(db, result.payment_id, result.succeeded, result.transaction_id)
    return to_out(db, payment, order)


def webhook(db: Session, provider_name: str, payload: dict[str, Any]) -> None:
    if provider_name == "mock":
        # The mock "webhook" is the authenticated confirm/fail pair, never a public endpoint.
        raise NotFoundError("payment_provider", "Use /payments/mock/{id}/confirm")
    result = get_provider(provider_name).handle_webhook(payload)
    settle(db, result.payment_id, result.succeeded, result.transaction_id)


def refund_order(db: Session, order: Order) -> None:
    provider = get_provider()
    for payment in db.scalars(
        select(Payment).where(
            Payment.order_id == order.id, Payment.status == PaymentStatus.succeeded
        )
    ):
        if provider.refund(payment):
            payment.status = PaymentStatus.refunded
            payment.completed_at = clock.now_utc()


def fail_pending(db: Session, order: Order) -> None:
    for payment in db.scalars(
        select(Payment).where(Payment.order_id == order.id, Payment.status == PaymentStatus.pending)
    ):
        payment.status = PaymentStatus.failed
        payment.completed_at = clock.now_utc()
