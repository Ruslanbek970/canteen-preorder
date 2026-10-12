"""After the k6 rush: nothing oversold, counters match the orders (SPEC 13).

python -m scripts.load_check   (exit code 1 if an invariant is broken)
"""

import sys

from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import Canteen, MenuItem, Order, OrderItem, OrderStatus, PickupSlot

ACTIVE = (
    OrderStatus.pending_payment,
    OrderStatus.paid,
    OrderStatus.cooking,
    OrderStatus.ready,
    OrderStatus.picked_up,
)


def main() -> int:
    with SessionLocal() as db:
        canteen = db.scalar(
            select(Canteen).where(Canteen.slug.like("load-%")).order_by(Canteen.id.desc())
        )
        if canteen is None:
            print("no load-test canteen: run scripts.load_setup first")
            return 1
        problems = []
        booked = dict(
            db.execute(
                select(Order.pickup_slot_id, func.count(Order.id))
                .where(Order.canteen_id == canteen.id, Order.status.in_(ACTIVE))
                .group_by(Order.pickup_slot_id)
            ).all()
        )
        slot_rows = db.scalars(
            select(PickupSlot).where(PickupSlot.canteen_id == canteen.id).order_by(PickupSlot.id)
        ).all()
        print("slot   booked/capacity  orders")
        for slot in slot_rows:
            orders = booked.get(slot.id, 0)
            print(f"{slot.starts_at:%H:%M}  {slot.booked_count:>6}/{slot.capacity:<8} {orders}")
            if slot.booked_count > slot.capacity:
                problems.append(f"slot {slot.id} overbooked")
            if slot.booked_count != orders:
                problems.append(f"slot {slot.id}: counter {slot.booked_count} != {orders} orders")
        sold = dict(
            db.execute(
                select(OrderItem.menu_item_id, func.sum(OrderItem.quantity))
                .join(Order, Order.id == OrderItem.order_id)
                .where(Order.canteen_id == canteen.id, Order.status.in_(ACTIVE))
                .group_by(OrderItem.menu_item_id)
            ).all()
        )
        print("menu item  available/planned  sold")
        for mi in db.scalars(select(MenuItem).where(MenuItem.canteen_id == canteen.id)):
            taken = int(sold.get(mi.id, 0))
            print(f"{mi.id:>9}  {mi.available_portions:>9}/{mi.planned_portions:<7} {taken}")
            if mi.available_portions < 0:
                problems.append(f"menu item {mi.id} below zero")
            if mi.planned_portions - mi.available_portions != taken:
                problems.append(f"menu item {mi.id}: counter does not match {taken} sold")
        total = sum(booked.values())
        print(f"orders placed: {total}")
    if problems:
        print("FAILED:", *problems, sep="\n  ")
        return 1
    print("OK: booked_count <= capacity, available_portions >= 0, counters match the orders")
    return 0


if __name__ == "__main__":
    sys.exit(main())
