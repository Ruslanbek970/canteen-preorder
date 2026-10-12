from datetime import date

from sqlalchemy import func, select

from app.models import (
    AllergySeverity,
    Canteen,
    DishReview,
    MenuItem,
    Order,
    OrderChannel,
    OrderItem,
    OrderStatus,
    OrderStatusHistory,
    PickupSlot,
    User,
    UserRole,
    WasteRecord,
)
from ml import synthetic_history as sh


def _setup(db, factory, freeze):
    freeze("2026-10-12 10:00")  # Monday
    canteen = factory.canteen(slug="main")
    factory.user(UserRole.cook, canteen=canteen)
    nuts = factory.allergen("nuts")
    for name, shelf in (("Плов", 4), ("Самса", 6), ("Чай с молоком", 2)):
        factory.dish(name_ru=name, price=500, shelf_life_hours=shelf)
    honey_cake = factory.dish(name_ru="Медовик", price=700, shelf_life_hours=24, allergens=[nuts])
    student = factory.user(email="student@demo.kz")
    factory.user_allergen(student, nuts, AllergySeverity.severe)
    return canteen, student, honey_cake


def test_one_week_of_history(db, factory, freeze):
    canteen, student, honey_cake = _setup(db, factory, freeze)
    result = sh.generate(db, canteen, weeks=1)
    assert result.days == [date(2026, 10, d) for d in (5, 6, 7, 8, 9)]
    assert result.stats.orders > 500 and result.stats.reviews > 0

    days = set(db.scalars(select(Order.service_date).distinct()))
    assert days == set(result.days)
    db.refresh(canteen)
    assert canteen.synthetic_history_until == date(2026, 10, 9)

    # Slots never overflow and their counters match the orders.
    booked = dict(
        db.execute(
            select(Order.pickup_slot_id, func.count(Order.id))
            .where(Order.status != OrderStatus.cancelled, Order.pickup_slot_id.is_not(None))
            .group_by(Order.pickup_slot_id)
        ).all()
    )
    for slot in db.scalars(select(PickupSlot)):
        assert slot.booked_count == booked.get(slot.id, 0) <= slot.capacity

    # Nothing is sold beyond what was cooked, and the books balance.
    for mi in db.scalars(select(MenuItem)):
        sold = db.scalar(
            select(func.coalesce(func.sum(OrderItem.quantity), 0))
            .join(Order, Order.id == OrderItem.order_id)
            .where(OrderItem.menu_item_id == mi.id, Order.status != OrderStatus.cancelled)
        )
        thrown = db.scalar(
            select(func.coalesce(func.sum(WasteRecord.portions), 0)).where(
                WasteRecord.menu_item_id == mi.id
            )
        )
        assert sold <= mi.planned_portions
        assert mi.available_portions >= 0
        no_show = db.scalar(
            select(func.coalesce(func.sum(OrderItem.quantity), 0))
            .join(Order, Order.id == OrderItem.order_id)
            .where(OrderItem.menu_item_id == mi.id, Order.status == OrderStatus.no_show)
        )
        assert mi.planned_portions - sold == thrown - no_show + mi.available_portions

    # The demo student never got the dish they are allergic to.
    unsafe = db.scalar(
        select(func.count(OrderItem.id))
        .join(Order, Order.id == OrderItem.order_id)
        .join(MenuItem, MenuItem.id == OrderItem.menu_item_id)
        .where(Order.user_id == student.id, MenuItem.dish_id == honey_cake.id)
    )
    assert unsafe == 0
    assert db.scalar(select(func.count(Order.id)).where(Order.user_id == student.id)) > 0

    # Synthetic customers cannot sign in; till sales have no customer.
    synthetic = db.scalars(select(User).where(User.email.like("%@synthetic.demo"))).all()
    assert len(synthetic) == sh.SYNTHETIC_CUSTOMERS and not any(u.is_active for u in synthetic)
    till = db.scalars(select(Order).where(Order.channel == OrderChannel.cashier)).all()
    assert till and all(o.user_id is None and o.status == OrderStatus.picked_up for o in till)

    # History timestamps are in the past, not when the script ran.
    latest = db.scalar(select(func.max(OrderStatusHistory.changed_at)))
    assert latest.date() <= date(2026, 10, 10)
    ratings = db.scalars(select(DishReview.rating)).all()
    assert set(ratings) <= {1, 2, 3, 4, 5}


def test_idempotent_and_skips_real_days(db, factory, freeze):
    canteen, *_ = _setup(db, factory, freeze)
    first = sh.generate(db, canteen, weeks=1)
    count = db.scalar(select(func.count(Order.id)))
    again = sh.generate(db, canteen, weeks=1)
    assert again.days == [] and db.scalar(select(func.count(Order.id))) == count
    # A wider window only adds the missing week.
    wider = sh.generate(db, canteen, weeks=2)
    assert wider.days == [date(2026, 9, 28 + i) for i in range(3)] + [
        date(2026, 10, 1),
        date(2026, 10, 2),
    ]
    assert first.days[0] == date(2026, 10, 5)


def test_generate_for_active_skips_e2e(db, factory, freeze):
    canteen, *_ = _setup(db, factory, freeze)
    e2e = factory.canteen(slug="e2e")
    assert sh.generate_for_active(db, weeks=1) == 5
    assert db.scalar(select(func.count(Order.id)).where(Order.canteen_id == e2e.id)) == 0
    assert sh.has_history(db)
    assert db.get(Canteen, canteen.id).synthetic_history_until is not None


def test_demand_patterns():
    monday, thursday, friday = date(2026, 10, 5), date(2026, 10, 8), date(2026, 10, 9)
    assert sh.expected_demand("Плов", thursday, 0) > sh.expected_demand("Плов", monday, 0)
    assert sh.expected_demand("Самса", friday, 0) < sh.expected_demand("Самса", monday, 0)
    assert sh.expected_demand("Самса", monday, 1) > sh.expected_demand("Самса", monday, 0)
    assert sh.expected_demand("Самса", date(2026, 10, 10), 0) == 0  # Saturday
    assert sh.slot_weight(sh.BREAKS[1][0]) > sh.OFF_BREAK_WEIGHT
