"""Test fixture for the Playwright e2e scenario (SPEC 13): a canteen open around the clock, so
the scenario passes whatever the time of day, with today's menu, slots and its own users.
Idempotent; safe to run before every e2e run. Not used by the app itself.

python -m scripts.e2e_setup
"""

from datetime import time, timedelta

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Building, Canteen, Dish, MenuItem, User, UserRole
from app.security import hash_password
from app.services import slots
from app.utils import time as clock
from scripts.seed import DEMO_PASSWORD

E2E_SLUG = "e2e"
DISHES = ("Плов", "Самса")
PORTIONS = 500


def _user(db, email: str, name: str, role: UserRole, canteen: Canteen | None) -> None:
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(
            email=email,
            full_name=name,
            role=role,
            password_hash=hash_password(DEMO_PASSWORD),
            preferred_language="ru",
        )
        db.add(user)
    user.canteen_id = canteen.id if canteen else None
    user.email_verified_at = user.email_verified_at or clock.now_utc()
    user.is_active = True
    user.preferred_language = "ru"


def main() -> None:
    with SessionLocal() as db:
        canteen = db.scalar(select(Canteen).where(Canteen.slug == E2E_SLUG))
        if canteen is None:
            building = db.scalar(select(Building).order_by(Building.id).limit(1))
            if building is None:
                building = Building(name="Корпус e2e", address="—")
                db.add(building)
                db.flush()
            canteen = Canteen(
                building_id=building.id,
                name="Тестовая столовая (e2e)",
                opens_at=time(0, 0),
                closes_at=time(23, 59),
                default_slot_minutes=10,
                default_slot_capacity=200,
                order_cutoff_minutes=5,
                slug=E2E_SLUG,
            )
            db.add(canteen)
            db.flush()
        # Teachers see every slot (no lesson filter), so the scenario does not depend on the
        # timetable.
        _user(db, "e2e-customer@demo.kz", "E2E Покупатель", UserRole.teacher, None)
        _user(db, "e2e-cook@demo.kz", "E2E Повар", UserRole.cook, canteen)
        _user(db, "e2e-cashier@demo.kz", "E2E Кассир", UserRole.cashier, canteen)

        today = clock.today_local()
        for day in (today, today + timedelta(days=1)):
            for name in DISHES:
                dish = db.scalar(select(Dish).where(Dish.name_ru == name))
                if dish is None:
                    continue
                item = db.scalar(
                    select(MenuItem).where(
                        MenuItem.canteen_id == canteen.id,
                        MenuItem.dish_id == dish.id,
                        MenuItem.menu_date == day,
                    )
                )
                if item is None:
                    item = MenuItem(
                        canteen_id=canteen.id,
                        dish_id=dish.id,
                        menu_date=day,
                        price=dish.base_price,
                        planned_portions=PORTIONS,
                        available_portions=PORTIONS,
                    )
                    db.add(item)
                else:
                    item.available_portions = max(item.available_portions, 50)
                    item.planned_portions = max(item.planned_portions, item.available_portions)
        db.commit()
        slots.generate_slots(db, canteen, today)
        slots.generate_slots(db, canteen, today + timedelta(days=1))
        print(f"e2e canteen {canteen.id} ready")


if __name__ == "__main__":
    main()
