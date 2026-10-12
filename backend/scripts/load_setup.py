"""Data for the k6 order rush (SPEC 13): a fresh canteen with 6 slots of 30 places in the next
hour and three dishes of 60 portions, and 500 verified students with access tokens.

python -m scripts.load_setup [--users 500] [--out load_users.json]

Each run makes a new canteen `load-<time>` and switches the previous ones off, so runs do not
mix. Tokens live as long as ACCESS_TOKEN_MINUTES (15 by default): run k6 right after.
Not used by the app itself; never run it on production data.
"""

import argparse
import json
from datetime import date, datetime, time, timedelta

from sqlalchemy import select, update

from app.db import SessionLocal
from app.models import Building, Canteen, Dish, MenuItem, StudentGroup, User, UserRole
from app.security import create_access_token, hash_password
from app.services import slots
from app.utils import time as clock

SLOTS = 6
SLOT_MINUTES = 10
CAPACITY = 30
DISHES = ("Плов", "Самса", "Чай с молоком")
PORTIONS = 60
GROUP = "LOAD-1"
DOMAIN = "load.demo"


def _window(now: datetime) -> tuple[date, time, time]:
    """The next hour of slots, starting at least 20 minutes from now, on a 10-minute grid.
    Late in the evening the hour does not fit into today: then it is tomorrow at noon."""
    start = now + timedelta(minutes=20)
    start = start.replace(second=0, microsecond=0) + timedelta(minutes=-start.minute % 10)
    end = start + timedelta(minutes=SLOTS * SLOT_MINUTES)
    if end.date() != now.date() or end.time() == time(0):
        start = datetime.combine(now.date() + timedelta(days=1), time(12, 0), now.tzinfo)
        end = start + timedelta(minutes=SLOTS * SLOT_MINUTES)
    return start.date(), start.time(), end.time()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--users", type=int, default=500)
    parser.add_argument("--out", default="load_users.json")
    args = parser.parse_args()

    now = clock.now_local()
    day, opens, closes = _window(now)
    with SessionLocal() as db:
        db.execute(update(Canteen).where(Canteen.slug.like("load-%")).values(is_active=False))
        building = db.scalar(select(Building).order_by(Building.id).limit(1))
        if building is None:
            building = Building(name="Корпус (нагрузка)")
            db.add(building)
            db.flush()
        canteen = Canteen(
            building_id=building.id,
            name=f"Нагрузочный тест {now:%H:%M}",
            slug=f"load-{now:%Y%m%d%H%M%S}",
            opens_at=opens,
            closes_at=closes,
            default_slot_minutes=SLOT_MINUTES,
            default_slot_capacity=CAPACITY,
            order_cutoff_minutes=5,
        )
        db.add(canteen)
        db.flush()
        menu = []
        for name in DISHES:
            dish = db.scalar(select(Dish).where(Dish.name_ru == name))
            if dish is None:
                raise SystemExit(f"dish {name!r} not found: run `make seed` first")
            item = MenuItem(
                canteen_id=canteen.id,
                dish_id=dish.id,
                menu_date=day,
                price=dish.base_price,
                planned_portions=PORTIONS,
                available_portions=PORTIONS,
            )
            db.add(item)
            menu.append(item)
        group = db.scalar(select(StudentGroup).where(StudentGroup.code == GROUP))
        if group is None:
            group = StudentGroup(code=GROUP)  # no lessons: every slot suits them
            db.add(group)
            db.flush()
        existing = {
            u.email: u for u in db.scalars(select(User).where(User.email.like(f"%@{DOMAIN}")))
        }
        password = hash_password("demo1234")
        users = []
        for n in range(1, args.users + 1):
            email = f"load-{n:03d}@{DOMAIN}"
            user = existing.get(email)
            if user is None:
                user = User(
                    email=email,
                    full_name=f"Нагрузка {n:03d}",
                    password_hash=password,
                    role=UserRole.student,
                    group_id=group.id,
                    email_verified_at=clock.now_utc(),
                )
                db.add(user)
            users.append(user)
        db.commit()
        created = slots.generate_slots(db, canteen, day)
        payload = {
            "canteen_id": canteen.id,
            "date": day.isoformat(),
            "menu_item_ids": [mi.id for mi in menu],
            "tokens": [create_access_token(u) for u in users],
        }
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh)
    print(
        f"canteen {payload['canteen_id']}: {created} slots {day} {opens:%H:%M}-{closes:%H:%M} x "
        f"{CAPACITY}, {len(DISHES)} dishes x {PORTIONS}; {len(users)} students -> {args.out}"
    )


if __name__ == "__main__":
    main()
