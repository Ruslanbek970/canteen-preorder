from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import select

from app.errors import ConflictError, NotFoundError, ValidationError
from app.models import (
    Notification,
    Order,
    OrderItem,
    OrderStatus,
    Promotion,
    PromotionStatus,
    PromotionType,
    UserRole,
)
from app.schemas.promotions import OffPeakCreate
from app.services import menu, promotions
from app.utils import time as clock
from worker import jobs

DAY = date(2026, 10, 12)


def local(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=clock.local_tz())


@pytest.fixture
def p(factory, freeze):
    freeze("2026-10-12 14:00")
    canteen = factory.canteen()  # closes 17:00
    manager = factory.user(UserRole.canteen_manager, canteen=canteen)
    samsa = factory.dish(name_ru="Самса", name_kk="Самса kk", shelf_life_hours=3)
    leftover = factory.menu_item(
        canteen, samsa, day=DAY, portions=20, planned=40, cooked_at=local("2026-10-12 12:00")
    )
    return {"canteen": canteen, "manager": manager, "samsa": samsa, "leftover": leftover}


def test_leftover_proposed_once_for_dishes_that_spoil_soon(db, factory, p, freeze):
    canteen = p["canteen"]
    # Almost sold out: no discount.
    factory.menu_item(canteen, day=DAY, portions=5, planned=40, cooked_at=local("2026-10-12 12:00"))
    # Plenty left but keeps until tomorrow: no discount.
    factory.menu_item(
        canteen,
        factory.dish(shelf_life_hours=24),
        day=DAY,
        portions=30,
        planned=40,
        cooked_at=local("2026-10-12 12:00"),
    )
    # Not cooked yet: unknown expiry.
    factory.menu_item(canteen, day=DAY, portions=30, planned=40)

    freeze("2026-10-12 13:00")
    assert promotions.propose_leftover(db) == 0  # before 13:30
    freeze("2026-10-12 14:00")
    assert jobs.propose_leftover_discounts() == 1
    assert promotions.propose_leftover(db) == 0  # one proposal per dish
    promo = db.scalar(select(Promotion))
    assert promo.menu_item_id == p["leftover"].id and promo.status == PromotionStatus.proposed
    assert promo.discount_percent == 30 and promo.created_by_system
    assert promo.valid_to == local("2026-10-12 15:00")  # cooked 12:00 + 3 h


def test_leftover_ends_at_closing_time(db, factory, freeze):
    freeze("2026-10-12 15:30")
    canteen = factory.canteen()  # closes 17:00
    factory.menu_item(
        canteen,
        factory.dish(shelf_life_hours=3),
        day=DAY,
        portions=30,
        planned=40,
        cooked_at=local("2026-10-12 14:30"),
    )
    assert promotions.propose_leftover(db) == 1
    assert db.scalar(select(Promotion.valid_to)) == local("2026-10-12 17:00")
    freeze("2026-10-12 17:10")
    assert promotions.propose_leftover(db) == 0  # closed


def _buy(db, factory, canteen, menu_item, user, status=OrderStatus.picked_up, day=DAY):
    slot = factory.slot(canteen, day=day, starts=f"{9 + user.id % 8:02d}:00")
    order = Order(
        pickup_slot_id=slot.id,
        user_id=user.id,
        canteen_id=canteen.id,
        service_date=day,
        order_number=f"T-{user.id}",
        status=status,
        subtotal=menu_item.price,
        channel="mobile_app",
    )
    db.add(order)
    db.flush()
    db.add(
        OrderItem(
            order_id=order.id,
            menu_item_id=menu_item.id,
            quantity=1,
            unit_price=menu_item.price,
        )
    )
    db.commit()


def test_approve_leftover_tells_recent_buyers(db, factory, p):
    canteen, samsa = p["canteen"], p["samsa"]
    earlier = factory.menu_item(canteen, samsa, day=DAY - timedelta(days=3))
    buyer = factory.user()
    kk_buyer = factory.user(preferred_language="kk")
    opted_out = factory.user(marketing_opt_out=True)
    unpaid = factory.user()
    stale = factory.user()
    for user in (buyer, kk_buyer, opted_out):
        _buy(db, factory, canteen, earlier, user)
    _buy(db, factory, canteen, earlier, unpaid, status=OrderStatus.cancelled)
    old = factory.menu_item(canteen, samsa, day=DAY - timedelta(days=45))
    _buy(db, factory, canteen, old, stale, day=DAY - timedelta(days=45))

    promotions.propose_leftover(db)
    promo_id = db.scalar(select(Promotion.id))
    out = promotions.approve(db, p["manager"], canteen.id, promo_id)
    assert out.status == PromotionStatus.active and out.dish_name == "Самса"

    notes = {
        n.user_id: n
        for n in db.scalars(select(Notification).where(Notification.kind == "leftover_discount"))
    }
    assert set(notes) == {buyer.id, kk_buyer.id}
    assert notes[buyer.id].title == "Скидка 30% на Самса"
    assert notes[kk_buyer.id].title == "Самса kk үшін 30% жеңілдік"
    assert "до 15:00" in notes[buyer.id].body

    # The menu now shows the discounted price.
    item = next(
        i for i in menu.get_menu(db, canteen.id, DAY, None).items if i.id == p["leftover"].id
    )
    assert item.discount_percent == 30

    with pytest.raises(ConflictError) as err:
        promotions.reject(db, p["manager"], canteen.id, promo_id)
    assert err.value.code == "promotion_not_proposed"


def test_reject_is_final_and_expired_cannot_be_approved(db, p, freeze):
    promotions.propose_leftover(db)
    promo_id = db.scalar(select(Promotion.id))
    out = promotions.reject(db, p["manager"], p["canteen"].id, promo_id)
    assert out.status == PromotionStatus.rejected
    assert promotions.propose_leftover(db) == 0

    db.execute(
        Promotion.__table__.update().values(status=PromotionStatus.proposed)  # type: ignore[attr-defined]
    )
    db.commit()
    freeze("2026-10-12 15:30")
    with pytest.raises(ConflictError) as err:
        promotions.approve(db, p["manager"], p["canteen"].id, promo_id)
    assert err.value.code == "promotion_expired"
    assert promotions.expire_promotions(db) == 1
    assert db.scalar(select(Promotion.status)) == PromotionStatus.expired


def test_other_canteen_cannot_see_or_decide(db, factory, p):
    promotions.propose_leftover(db)
    promo_id = db.scalar(select(Promotion.id))
    other = factory.canteen()
    assert promotions.list_promotions(db, other.id) == []
    with pytest.raises(NotFoundError):
        promotions.approve(db, p["manager"], other.id, promo_id)


def test_off_peak_suggested_for_empty_slots_soon(db, factory, p):
    canteen = p["canteen"]
    empty = factory.slot(canteen, day=DAY, starts="14:40", capacity=30, booked=5)
    factory.slot(canteen, day=DAY, starts="14:50", capacity=30, booked=10)  # 33% full
    factory.slot(canteen, day=DAY, starts="15:10", capacity=30)  # more than an hour away
    factory.slot(canteen, day=DAY, starts="13:50", capacity=30)  # already started
    assert jobs.suggest_off_peak() == 1
    assert promotions.suggest_off_peak(db) == 0
    promo = db.scalar(select(Promotion))
    assert promo.pickup_slot_id == empty.id and promo.type == PromotionType.off_peak
    assert promo.discount_percent == 20 and promo.status == PromotionStatus.proposed
    assert promo.valid_to == local("2026-10-12 14:50")


def test_manager_creates_off_peak(db, factory, p):
    canteen = p["canteen"]
    slot = factory.slot(canteen, day=DAY, starts="15:00")
    out = promotions.create_off_peak(
        db, p["manager"], canteen.id, OffPeakCreate(pickup_slot_id=slot.id, discount_percent=15)
    )
    assert out.status == PromotionStatus.active and out.slot_starts_at.isoformat() == "15:00:00"
    assert not out.created_by_system
    past = factory.slot(canteen, day=DAY, starts="13:00")
    with pytest.raises(ValidationError):
        promotions.create_off_peak(
            db, p["manager"], canteen.id, OffPeakCreate(pickup_slot_id=past.id, discount_percent=15)
        )
    foreign = factory.slot(factory.canteen(), day=DAY, starts="15:00")
    with pytest.raises(NotFoundError):
        promotions.create_off_peak(
            db,
            p["manager"],
            canteen.id,
            OffPeakCreate(pickup_slot_id=foreign.id, discount_percent=15),
        )


def test_promotions_api(client, auth, db, factory, p):
    promotions.propose_leftover(db)
    h = auth(p["manager"])
    items = client.get("/api/v1/manager/promotions", headers=h).json()
    assert [i["status"] for i in items] == ["proposed"]
    assert items[0]["available_portions"] == 20 and items[0]["planned_portions"] == 40
    r = client.post(f"/api/v1/manager/promotions/{items[0]['id']}/approve", headers=h)
    assert r.status_code == 200 and r.json()["status"] == "active"
    again = client.post(f"/api/v1/manager/promotions/{items[0]['id']}/reject", headers=h)
    assert again.status_code == 409
    assert client.get("/api/v1/manager/promotions?status=proposed", headers=h).json() == []

    slot = factory.slot(p["canteen"], day=DAY, starts="16:00")
    bad = client.post(
        "/api/v1/manager/promotions",
        json={"pickup_slot_id": slot.id, "discount_percent": 90},
        headers=h,
    )
    assert bad.status_code == 422
    student = auth(factory.user())
    assert client.get("/api/v1/manager/promotions", headers=student).status_code == 403
