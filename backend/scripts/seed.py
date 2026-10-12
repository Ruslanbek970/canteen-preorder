"""Demo data (SPEC 5.4). Re-running wipes all tables and loads the demo set again.

python -m scripts.seed
"""

import logging
from datetime import date, time, timedelta
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import (
    Allergen,
    AllergySeverity,
    Base,
    Building,
    Canteen,
    ClassSchedule,
    Dish,
    DishCategory,
    DishIngredient,
    Ingredient,
    IngredientAllergen,
    MenuItem,
    StudentGroup,
    User,
    UserAllergen,
    UserRole,
)
from app.security import hash_password
from app.utils import time as clock

log = logging.getLogger(__name__)

DEMO_PASSWORD = "demo1234"

# Weekly timetable per group: (start, end, subject). Breaks between classes are pickup windows.
SCHEDULES = {
    "SE-2301": [
        ("09:00", "10:20", "Базы данных"),
        ("10:30", "11:50", "DevOps"),
        ("12:10", "13:30", "Архитектура ПО"),
        ("13:40", "15:00", "Английский язык"),
    ],
    "SE-2302": [
        ("09:00", "10:20", "Алгоритмы"),
        ("10:30", "12:00", "Веб-разработка"),
        ("12:30", "13:50", "Тестирование ПО"),
        ("14:00", "15:20", "Казахский язык"),
    ],
    "IT-2201": [
        ("10:00", "11:20", "Компьютерные сети"),
        ("11:30", "12:50", "Информационная безопасность"),
        ("13:20", "14:40", "Машинное обучение"),
    ],
}

CATEGORIES = [
    ("Супы", 1),
    ("Вторые блюда", 2),
    ("Салаты", 3),
    ("Выпечка и десерты", 4),
    ("Напитки", 5),
]

ALLERGENS = [
    ("gluten", "Глютен", "Глютен"),
    ("milk", "Молоко", "Сүт"),
    ("eggs", "Яйца", "Жұмыртқа"),
    ("nuts", "Орехи", "Жаңғақ"),
    ("soy", "Соя", "Соя"),
    ("fish", "Рыба", "Балық"),
    ("sesame", "Кунжут", "Күнжіт"),
    ("celery", "Сельдерей", "Балдыркөк"),
]

# name, unit, allergen codes
INGREDIENTS = [
    ("мука пшеничная", "g", ["gluten"]),
    ("говядина", "g", []),
    ("курица", "g", []),
    ("рис", "g", []),
    ("морковь", "g", []),
    ("лук", "g", []),
    ("картофель", "g", []),
    ("яйцо", "pcs", ["eggs"]),
    ("молоко", "ml", ["milk"]),
    ("сливочное масло", "g", ["milk"]),
    ("майонез", "g", ["eggs"]),
    ("грецкий орех", "g", ["nuts"]),
    ("мёд", "g", []),
    ("помидор", "g", []),
    ("огурец", "g", []),
    ("чёрный чай", "g", []),
    ("сухофрукты", "g", []),
    ("сахар", "g", []),
    ("баранина", "g", []),
    ("колбаса", "g", ["soy"]),
    ("свёкла", "g", []),
    ("капуста", "g", []),
    ("сметана", "g", ["milk"]),
    ("кунжут", "g", ["sesame"]),
]

# category, name_ru, name_kk, price, grams, kcal, protein, fat, carbs, shelf life h, veg,
# description, recipe [(ingredient, qty)], planned portions per day
# fmt: off
DISHES = [
    (1, "Куриный суп", "Тауық сорпасы", 900, 300, 180, "12.0", "6.0", "18.0", 4, False,
     "Лёгкий суп на курином бульоне с домашней лапшой.",
     [("курица", 80), ("картофель", 60), ("морковь", 20), ("лук", 15), ("мука пшеничная", 20)],
     60),
    (1, "Борщ", "Борщ", 950, 300, 210, "8.0", "9.0", "22.0", 6, False,
     "Борщ на говяжьем бульоне со сметаной.",
     [("говядина", 60), ("свёкла", 60), ("капуста", 50), ("картофель", 40), ("сметана", 20)],
     40),
    (2, "Лагман", "Лағман", 1600, 400, 620, "28.0", "22.0", "75.0", 3, False,
     "Тянутая лапша с говядиной и овощами.",
     [("мука пшеничная", 150), ("говядина", 100), ("морковь", 30), ("лук", 30), ("помидор", 40)],
     90),
    (2, "Плов", "Палау", 1500, 350, 650, "22.0", "26.0", "80.0", 4, False,
     "Плов с бараниной и жёлтой морковью.",
     [("рис", 150), ("баранина", 100), ("морковь", 60), ("лук", 30)],
     110),
    (2, "Манты", "Манты", 1400, 300, 540, "24.0", "24.0", "52.0", 3, False,
     "Манты с говядиной и луком, 5 штук.",
     [("мука пшеничная", 120), ("говядина", 110), ("лук", 50)],
     50),
    (3, "Оливье", "Оливье", 800, 200, 310, "9.0", "24.0", "14.0", 6, False,
     "Классический салат с колбасой и майонезом.",
     [("картофель", 70), ("яйцо", 1), ("майонез", 30), ("колбаса", 40), ("морковь", 20)],
     35),
    (3, "Овощной салат", "Көкөніс салаты", 600, 200, 90, "2.0", "5.0", "9.0", 4, True,
     "Помидоры и огурцы с зеленью.",
     [("помидор", 100), ("огурец", 100)],
     25),
    (4, "Самса", "Самса", 450, 150, 380, "14.0", "20.0", "36.0", 6, False,
     "Слоёная самса с бараниной, посыпанная кунжутом.",
     [("мука пшеничная", 80), ("сливочное масло", 15), ("баранина", 50), ("лук", 20),
      ("кунжут", 3)],
     120),
    (4, "Медовик", "Бал торты", 700, 120, 420, "6.0", "22.0", "50.0", 24, True,
     "Медовый торт с грецким орехом.",
     [("мука пшеничная", 50), ("мёд", 20), ("яйцо", 1), ("сливочное масло", 20),
      ("грецкий орех", 10)],
     30),
    (5, "Чай с молоком", "Сүтті шай", 250, 250, 70, "3.0", "3.0", "8.0", 2, True,
     "Чёрный чай с молоком по-казахски.",
     [("чёрный чай", 3), ("молоко", 50), ("сахар", 5)],
     150),
    (5, "Компот", "Компот", 300, 250, 110, "0.0", "0.0", "27.0", 8, True,
     "Компот из сухофруктов.",
     [("сухофрукты", 40), ("сахар", 15)],
     100),
]

FIRST_NAMES = [
    "Айгерим", "Нурсултан", "Дана", "Ерасыл", "Алия", "Арман", "Жанна", "Бекзат", "Камила",
    "Ильяс", "Сабина", "Темирлан", "Асель", "Даулет", "Мадина", "Алихан", "Аружан", "Санжар",
    "Инкар", "Расул",
]
LAST_NAMES = [
    "Ахметова", "Серікұлы", "Нурланова", "Жумабеков", "Касымова", "Омаров", "Садыкова",
    "Беков", "Ибраимова", "Тулегенов", "Есенова", "Абенов", "Мусина", "Кенжебаев",
    "Алиева", "Рахимов", "Сейтқали", "Утебаев", "Бекова", "Исаев",
]
# fmt: on


def _t(value: str) -> time:
    return time.fromisoformat(value)


def wipe(db: Session) -> None:
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    db.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


def seed_campus(db: Session) -> dict[str, object]:
    main = Building(name="Главный корпус", address="Кампус, блок А")
    it = Building(name="IT-корпус", address="Кампус, блок C")
    db.add_all([main, it])
    db.flush()
    canteen = Canteen(
        building_id=main.id,
        name="Главная столовая",
        opens_at=_t("09:00"),
        closes_at=_t("17:00"),
        default_slot_minutes=10,
        default_slot_capacity=30,
        pickup_shelves_count=10,
        order_cutoff_minutes=15,
        slug="main",
    )
    db.add(canteen)
    groups = {
        "SE-2301": StudentGroup(code="SE-2301", faculty="Программная инженерия", study_year=3),
        "SE-2302": StudentGroup(code="SE-2302", faculty="Программная инженерия", study_year=3),
        "IT-2201": StudentGroup(code="IT-2201", faculty="Информационные технологии", study_year=4),
    }
    db.add_all(groups.values())
    db.flush()
    for code, lessons in SCHEDULES.items():
        for day in range(1, 6):
            for start, end, subject in lessons:
                db.add(
                    ClassSchedule(
                        group_id=groups[code].id,
                        day_of_week=day,
                        starts_at=_t(start),
                        ends_at=_t(end),
                        building_id=it.id,
                        subject=subject,
                    )
                )
    return {"canteen": canteen, "groups": groups, "buildings": [main, it]}


def seed_food(db: Session) -> dict[str, object]:
    categories = [DishCategory(name=n, sort_order=o) for n, o in CATEGORIES]
    allergens = {c: Allergen(code=c, name_ru=ru, name_kk=kk) for c, ru, kk in ALLERGENS}
    ingredients = {n: Ingredient(name=n, unit=u) for n, u, _ in INGREDIENTS}
    db.add_all([*categories, *allergens.values(), *ingredients.values()])
    db.flush()
    for name, _unit, codes in INGREDIENTS:
        for code in codes:
            db.add(
                IngredientAllergen(
                    ingredient_id=ingredients[name].id, allergen_id=allergens[code].id
                )
            )
    dishes: list[tuple[Dish, int]] = []
    for row in DISHES:
        cat, name_ru, name_kk, price, grams, kcal, prot, fat, carbs, shelf, veg, desc = row[:12]
        recipe, planned = row[12], row[13]
        dish = Dish(
            category_id=categories[cat - 1].id,
            name_ru=name_ru,
            name_kk=name_kk,
            description=desc,
            base_price=Decimal(price),
            portion_grams=grams,
            calories=kcal,
            protein_g=Decimal(prot),
            fat_g=Decimal(fat),
            carbs_g=Decimal(carbs),
            shelf_life_hours=shelf,
            is_vegetarian=veg,
            is_halal=True,
        )
        dish.recipe = [
            DishIngredient(ingredient_id=ingredients[i].id, quantity=Decimal(q)) for i, q in recipe
        ]
        db.add(dish)
        dishes.append((dish, planned))
    db.flush()
    return {"dishes": dishes, "allergens": allergens}


def seed_users(db: Session, campus: dict, food: dict) -> dict[str, User]:
    canteen: Canteen = campus["canteen"]  # type: ignore[assignment]
    groups: dict[str, StudentGroup] = campus["groups"]  # type: ignore[assignment]
    pw = hash_password(DEMO_PASSWORD)
    now = clock.now_utc()

    def user(email: str, name: str, role: UserRole, **kw: object) -> User:
        u = User(
            email=email,
            full_name=name,
            password_hash=pw,
            role=role,
            email_verified_at=now,
            **kw,
        )
        db.add(u)
        return u

    users = {
        "student": user(
            "student@demo.kz",
            "Данияр Омаров",
            UserRole.student,
            group_id=groups["SE-2301"].id,
            health_data_consent_at=now,
        ),
        "teacher": user("teacher@demo.kz", "Аскар Ибраимов", UserRole.teacher),
        "cook": user(
            "cook@demo.kz",
            "Гульнара Садыкова",
            UserRole.cook,
            canteen_id=canteen.id,
            preferred_language="kk",
        ),
        "cashier": user(
            "cashier@demo.kz", "Ерлан Жаксыбеков", UserRole.cashier, canteen_id=canteen.id
        ),
        "manager": user(
            "manager@demo.kz", "Сауле Нурланова", UserRole.canteen_manager, canteen_id=canteen.id
        ),
        "admin": user("admin@demo.kz", "Администратор", UserRole.admin, preferred_language="en"),
    }
    group_codes = list(groups)
    for i in range(20):
        code = group_codes[i % len(group_codes)]
        users[f"student{i + 1:02d}"] = user(
            f"student{i + 1:02d}@demo.kz",
            f"{FIRST_NAMES[i]} {LAST_NAMES[i]}",
            UserRole.student,
            group_id=groups[code].id,
            preferred_language=["ru", "kk", "en"][i % 3] if i % 4 == 0 else "ru",
        )
    db.flush()
    allergens: dict[str, Allergen] = food["allergens"]  # type: ignore[assignment]
    # Demo student: severe nut allergy (red mark on Медовик), mild milk allergy (warning).
    db.add(
        UserAllergen(
            user_id=users["student"].id,
            allergen_id=allergens["nuts"].id,
            severity=AllergySeverity.severe,
        )
    )
    db.add(
        UserAllergen(
            user_id=users["student"].id,
            allergen_id=allergens["milk"].id,
            severity=AllergySeverity.mild,
        )
    )
    return users


def seed_menu(db: Session, canteen: Canteen, dishes: list[tuple[Dish, int]], day: date) -> None:
    cooked = clock.combine_local(day, _t("08:30"))
    for dish, planned in dishes:
        db.add(
            MenuItem(
                canteen_id=canteen.id,
                dish_id=dish.id,
                menu_date=day,
                price=dish.base_price,
                planned_portions=planned,
                available_portions=planned,
                cooked_at=cooked,
            )
        )


def run(db: Session) -> None:
    wipe(db)
    campus = seed_campus(db)
    food = seed_food(db)
    seed_users(db, campus, food)
    canteen: Canteen = campus["canteen"]  # type: ignore[assignment]
    today = clock.today_local()
    for day in (today, today + timedelta(days=1)):
        seed_menu(db, canteen, food["dishes"], day)  # type: ignore[arg-type]
    db.commit()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    with SessionLocal() as db:
        run(db)
    print(f"Demo data loaded. Password for all demo accounts: {DEMO_PASSWORD}")


if __name__ == "__main__":
    main()
