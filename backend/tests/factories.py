"""Small helpers to create test data directly through the ORM."""

from datetime import date, time, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import (
    Allergen,
    AllergySeverity,
    Building,
    Canteen,
    ClassSchedule,
    Dish,
    DishCategory,
    DishIngredient,
    Ingredient,
    IngredientAllergen,
    MenuItem,
    PickupSlot,
    StudentGroup,
    User,
    UserAllergen,
    UserRole,
)
from app.security import hash_password
from app.utils import time as clock

PASSWORD = "demo1234"
_PASSWORD_HASH = hash_password(PASSWORD)


class Factory:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._n = 0

    def _seq(self) -> int:
        self._n += 1
        return self._n

    def commit(self) -> None:
        self.db.commit()

    # ---- campus ---------------------------------------------------------
    def building(self, name: str | None = None) -> Building:
        b = Building(name=name or f"Building {self._seq()}")
        self.db.add(b)
        self.db.flush()
        return b

    def canteen(self, **kw: object) -> Canteen:
        building = kw.pop("building", None) or self.building()
        n = self._seq()
        c = Canteen(
            building_id=building.id,  # type: ignore[attr-defined]
            name=kw.pop("name", f"Canteen {n}"),
            opens_at=kw.pop("opens_at", time(9, 0)),
            closes_at=kw.pop("closes_at", time(17, 0)),
            slug=kw.pop("slug", f"c{n}"),
            **kw,
        )
        self.db.add(c)
        self.db.commit()
        return c

    def group(self, code: str | None = None) -> StudentGroup:
        g = StudentGroup(code=code or f"GR-{self._seq()}")
        self.db.add(g)
        self.db.commit()
        return g

    def lesson(
        self, group: StudentGroup, day_of_week: int, starts: str, ends: str
    ) -> ClassSchedule:
        lesson = ClassSchedule(
            group_id=group.id,
            day_of_week=day_of_week,
            starts_at=time.fromisoformat(starts),
            ends_at=time.fromisoformat(ends),
            building_id=self.building().id,
        )
        self.db.add(lesson)
        self.db.commit()
        return lesson

    def user(
        self,
        role: UserRole = UserRole.student,
        *,
        email: str | None = None,
        canteen: Canteen | None = None,
        group: StudentGroup | None = None,
        verified: bool = True,
        **kw: object,
    ) -> User:
        n = self._seq()
        if role == UserRole.student and group is None:
            group = self.group()
        if role in (UserRole.cook, UserRole.cashier, UserRole.canteen_manager) and canteen is None:
            canteen = self.canteen()
        u = User(
            email=email or f"{role.value}{n}@demo.kz",
            full_name=kw.pop("full_name", f"User {n}"),
            password_hash=_PASSWORD_HASH,
            role=role,
            group_id=group.id if group else None,
            canteen_id=canteen.id if canteen else None,
            email_verified_at=clock.now_utc() if verified else None,
            **kw,
        )
        self.db.add(u)
        self.db.commit()
        return u

    # ---- food -----------------------------------------------------------
    def category(self, name: str | None = None) -> DishCategory:
        c = DishCategory(name=name or f"Category {self._seq()}")
        self.db.add(c)
        self.db.flush()
        return c

    def allergen(self, code: str | None = None) -> Allergen:
        n = self._seq()
        a = Allergen(code=code or f"a{n}", name_ru=f"Аллерген {n}")
        self.db.add(a)
        self.db.commit()
        return a

    def ingredient(self, allergens: list[Allergen] | None = None) -> Ingredient:
        i = Ingredient(name=f"ingredient {self._seq()}", unit="g")
        self.db.add(i)
        self.db.flush()
        for a in allergens or []:
            self.db.add(IngredientAllergen(ingredient_id=i.id, allergen_id=a.id))
        self.db.commit()
        return i

    def dish(
        self,
        *,
        price: int | str = 1000,
        allergens: list[Allergen] | None = None,
        category: DishCategory | None = None,
        **kw: object,
    ) -> Dish:
        d = Dish(
            category_id=(category or self.category()).id,
            name_ru=kw.pop("name_ru", f"Блюдо {self._seq()}"),
            base_price=Decimal(str(price)),
            **kw,
        )
        self.db.add(d)
        self.db.flush()
        if allergens:
            ing = self.ingredient(allergens)
            self.db.add(DishIngredient(dish_id=d.id, ingredient_id=ing.id, quantity=Decimal(10)))
        self.db.commit()
        return d

    def menu_item(
        self,
        canteen: Canteen,
        dish: Dish | None = None,
        *,
        day: date | None = None,
        portions: int = 50,
        price: int | str | None = None,
        **kw: object,
    ) -> MenuItem:
        dish = dish or self.dish()
        mi = MenuItem(
            canteen_id=canteen.id,
            dish_id=dish.id,
            menu_date=day or clock.today_local(),
            price=Decimal(str(price)) if price is not None else dish.base_price,
            planned_portions=kw.pop("planned", portions),
            available_portions=portions,
            **kw,
        )
        self.db.add(mi)
        self.db.commit()
        return mi

    def slot(
        self,
        canteen: Canteen,
        *,
        day: date | None = None,
        starts: str = "12:00",
        minutes: int = 10,
        capacity: int = 30,
        booked: int = 0,
    ) -> PickupSlot:
        start = time.fromisoformat(starts)
        end = clock.combine_local(day or clock.today_local(), start) + timedelta(minutes=minutes)
        s = PickupSlot(
            canteen_id=canteen.id,
            slot_date=day or clock.today_local(),
            starts_at=start,
            ends_at=end.time(),
            capacity=capacity,
            booked_count=booked,
        )
        self.db.add(s)
        self.db.commit()
        return s

    def user_allergen(
        self, user: User, allergen: Allergen, severity: AllergySeverity = AllergySeverity.severe
    ) -> None:
        if user.health_data_consent_at is None:
            user.health_data_consent_at = clock.now_utc()
        self.db.add(UserAllergen(user_id=user.id, allergen_id=allergen.id, severity=severity))
        self.db.commit()
