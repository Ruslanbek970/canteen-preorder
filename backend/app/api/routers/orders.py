from datetime import date

from fastapi import APIRouter

from app.api.deps import DB, Customer, Page
from app.schemas.orders import OrderCreate, OrderList, OrderOut, RepeatResponse
from app.schemas.payments import PaymentOut
from app.services import orders as order_service
from app.services import payments

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=OrderOut, status_code=201)
def create_order(data: OrderCreate, user: Customer, db: DB) -> OrderOut:
    """One transaction: allergies -> portions -> slot -> number -> order -> payment (SPEC 7.5)."""
    return order_service.create_order(db, user, data)


@router.get("", response_model=OrderList)
def my_orders(user: Customer, db: DB, page: Page) -> OrderList:
    limit, offset = page
    return order_service.list_orders(db, user, limit, offset)


@router.get("/{order_id}", response_model=OrderOut)
def get_order(order_id: int, user: Customer, db: DB) -> OrderOut:
    return order_service.order_out(db, order_service.get_order_for(db, user, order_id))


@router.post("/{order_id}/cancel", response_model=OrderOut)
def cancel_order(order_id: int, user: Customer, db: DB) -> OrderOut:
    return order_service.cancel_order(db, user, order_id)


@router.post("/{order_id}/repeat", response_model=RepeatResponse)
def repeat_order(order_id: int, user: Customer, db: DB, date: date | None = None) -> RepeatResponse:
    return order_service.repeat_order(db, user, order_id, date)


@router.post("/{order_id}/pay", response_model=PaymentOut)
def pay_order(order_id: int, user: Customer, db: DB) -> PaymentOut:
    """A payment link for an unpaid order (again after «Отказ»)."""
    return payments.start_payment(db, user, order_id)
