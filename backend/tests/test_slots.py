from datetime import date, time

from sqlalchemy import func, select

from app.models import PickupSlot, UserRole
from app.services import slots

DAY = date(2026, 10, 12)  # Monday


def test_generate_slots_is_idempotent(db, factory):
    canteen = factory.canteen(opens_at=time(11, 0), closes_at=time(12, 0), default_slot_minutes=15)
    assert slots.generate_slots(db, canteen, DAY) == 4
    assert slots.generate_slots(db, canteen, DAY) == 0
    starts = db.scalars(
        select(PickupSlot.starts_at)
        .where(PickupSlot.canteen_id == canteen.id)
        .order_by("starts_at")
    ).all()
    assert starts == [time(11, 0), time(11, 15), time(11, 30), time(11, 45)]


def test_generate_keeps_bookings(db, factory):
    canteen = factory.canteen(opens_at=time(12, 0), closes_at=time(12, 20))
    factory.slot(canteen, day=DAY, starts="12:00", booked=5)
    assert slots.generate_slots(db, canteen, DAY) == 1
    booked = db.scalar(select(PickupSlot.booked_count).where(PickupSlot.starts_at == time(12, 0)))
    assert booked == 5


def test_student_with_lesson_does_not_see_overlapping_slot(client, factory, auth, freeze):
    """SPEC phase 3 'done when': a free student sees 12:00, a student in class does not."""
    freeze("2026-10-12 09:00")
    canteen = factory.canteen()
    slot = factory.slot(canteen, day=DAY, starts="12:00")
    busy_group = factory.group("SE-1")
    factory.lesson(busy_group, 1, "11:50", "13:10")
    busy = factory.user(group=busy_group)
    free = factory.user(group=factory.group("SE-2"))
    teacher = factory.user(UserRole.teacher)
    url = f"/api/v1/canteens/{canteen.id}/slots?date={DAY}"

    free_ids = [s["id"] for s in client.get(url, headers=auth(free)).json()["slots"]]
    assert free_ids == [slot.id]

    body = client.get(url, headers=auth(busy)).json()
    assert body["slots"] == []
    assert body["hidden"]["by_schedule"] == 1
    assert body["schedule_applied"] is True

    # Teachers see every available slot.
    teacher_body = client.get(url, headers=auth(teacher)).json()
    assert [s["id"] for s in teacher_body["slots"]] == [slot.id]
    assert teacher_body["schedule_applied"] is False


def test_lesson_on_other_weekday_does_not_hide(client, factory, auth, freeze):
    freeze("2026-10-12 09:00")
    canteen = factory.canteen()
    factory.slot(canteen, day=DAY, starts="12:00")
    group = factory.group()
    factory.lesson(group, 2, "11:50", "13:10")  # Tuesday
    student = factory.user(group=group)
    body = client.get(
        f"/api/v1/canteens/{canteen.id}/slots?date={DAY}", headers=auth(student)
    ).json()
    assert len(body["slots"]) == 1


def test_adjacent_lesson_does_not_overlap(client, factory, auth, freeze):
    freeze("2026-10-12 09:00")
    canteen = factory.canteen()
    factory.slot(canteen, day=DAY, starts="12:00", minutes=10)
    group = factory.group()
    factory.lesson(group, 1, "12:10", "13:30")  # starts exactly when the slot ends
    student = factory.user(group=group)
    body = client.get(
        f"/api/v1/canteens/{canteen.id}/slots?date={DAY}", headers=auth(student)
    ).json()
    assert len(body["slots"]) == 1


def test_cutoff_full_and_closed_are_hidden(client, factory, auth, freeze):
    freeze("2026-10-12 11:50")
    canteen = factory.canteen(order_cutoff_minutes=15)
    factory.slot(canteen, day=DAY, starts="12:00")  # starts in 10 min < cutoff
    factory.slot(canteen, day=DAY, starts="12:10", capacity=2, booked=2)  # full
    closed = factory.slot(canteen, day=DAY, starts="12:20")
    closed.is_closed = True
    factory.commit()
    ok = factory.slot(canteen, day=DAY, starts="12:30")
    user = factory.user(UserRole.teacher)
    body = client.get(f"/api/v1/canteens/{canteen.id}/slots?date={DAY}", headers=auth(user)).json()
    assert [s["id"] for s in body["slots"]] == [ok.id]
    assert body["hidden"] == {"by_schedule": 0, "too_late": 1, "full": 1, "closed": 1}
    assert body["total"] == 4


def test_slots_require_login(client, factory):
    canteen = factory.canteen()
    assert client.get(f"/api/v1/canteens/{canteen.id}/slots").status_code == 401


def test_manager_changes_capacity_and_closes(client, factory, auth, freeze):
    freeze("2026-10-12 09:00")
    manager = factory.user(UserRole.canteen_manager)
    slot = factory.slot(manager.canteen, day=DAY, starts="12:00", booked=3)
    h = auth(manager)
    r = client.patch(f"/api/v1/manager/slots/{slot.id}", json={"capacity": 40}, headers=h)
    assert r.status_code == 200 and r.json()["capacity"] == 40
    r = client.patch(f"/api/v1/manager/slots/{slot.id}", json={"capacity": 2}, headers=h)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "capacity_below_booked"
    r = client.patch(f"/api/v1/manager/slots/{slot.id}", json={"is_closed": True}, headers=h)
    assert r.json()["is_closed"] is True
    listed = client.get(f"/api/v1/manager/slots?date={DAY}", headers=h).json()
    assert [s["id"] for s in listed["slots"]] == [slot.id]


def test_manager_cannot_touch_other_canteen_slot(client, factory, auth):
    manager = factory.user(UserRole.canteen_manager)
    other = factory.slot(factory.canteen(), day=DAY)
    r = client.patch(
        f"/api/v1/manager/slots/{other.id}", json={"capacity": 5}, headers=auth(manager)
    )
    assert r.status_code == 404


def test_manager_generate_endpoint(client, factory, auth, db):
    manager = factory.user(UserRole.canteen_manager)
    r = client.post(f"/api/v1/manager/slots/generate?date={DAY}", headers=auth(manager))
    assert r.status_code == 200
    assert len(r.json()["slots"]) == 48  # 09:00-17:00 by 10 minutes
    count = db.scalar(select(func.count(PickupSlot.id)))
    assert count == 48


def test_student_cannot_manage_slots(client, factory, auth):
    student = factory.user()
    assert client.get("/api/v1/manager/slots", headers=auth(student)).status_code == 403


def test_book_and_release(db, factory):
    canteen = factory.canteen()
    slot = factory.slot(canteen, day=DAY, capacity=1)
    assert slots.book(db, slot.id) is True
    assert slots.book(db, slot.id) is False
    slots.release(db, slot.id)
    assert slots.book(db, slot.id) is True
    db.commit()
