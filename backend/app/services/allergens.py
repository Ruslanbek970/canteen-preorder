"""Rule-based allergy checks (SPEC 7.3): a dish's allergens are the union of its ingredients'
allergens. No ML is involved in deciding whether a dish is safe."""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Allergen,
    AllergySeverity,
    DishIngredient,
    IngredientAllergen,
    User,
    UserAllergen,
)


@dataclass
class AllergyAssessment:
    unsafe: bool = False  # a severe allergen: cannot be ordered
    warning: bool = False  # a mild/moderate allergen: needs allergy_warning_ack
    severe: list[Allergen] = field(default_factory=list)
    other: list[Allergen] = field(default_factory=list)


def dish_allergens(db: Session, dish_ids: Iterable[int]) -> dict[int, list[Allergen]]:
    ids = list(set(dish_ids))
    result: dict[int, list[Allergen]] = defaultdict(list)
    if not ids:
        return result
    rows = db.execute(
        select(DishIngredient.dish_id, Allergen)
        .join(IngredientAllergen, IngredientAllergen.ingredient_id == DishIngredient.ingredient_id)
        .join(Allergen, Allergen.id == IngredientAllergen.allergen_id)
        .where(DishIngredient.dish_id.in_(ids))
        .distinct()
        .order_by(DishIngredient.dish_id, Allergen.id)
    ).all()
    for dish_id, allergen in rows:
        result[dish_id].append(allergen)
    return result


def user_allergies(db: Session, user: User | None) -> dict[int, AllergySeverity]:
    if user is None or user.health_data_consent_at is None:
        return {}
    rows = db.execute(
        select(UserAllergen.allergen_id, UserAllergen.severity).where(
            UserAllergen.user_id == user.id
        )
    ).all()
    return {aid: sev for aid, sev in rows}


def assess(allergens: list[Allergen], mine: dict[int, AllergySeverity]) -> AllergyAssessment:
    result = AllergyAssessment()
    for a in allergens:
        severity = mine.get(a.id)
        if severity is None:
            continue
        if severity == AllergySeverity.severe:
            result.severe.append(a)
        else:
            result.other.append(a)
    result.unsafe = bool(result.severe)
    result.warning = bool(result.other)
    return result


def sticker_flag(db: Session, user_id: int | None) -> str | None:
    """The only allergy information the kitchen sees: «АЛЛЕРГИЯ: ОРЕХИ, МОЛОКО» (SPEC 6)."""
    if user_id is None:
        return None
    names = db.scalars(
        select(Allergen.name_ru)
        .join(UserAllergen, UserAllergen.allergen_id == Allergen.id)
        .join(User, User.id == UserAllergen.user_id)
        .where(UserAllergen.user_id == user_id, User.health_data_consent_at.is_not(None))
        .order_by(Allergen.name_ru)
    ).all()
    if not names:
        return None
    return "АЛЛЕРГИЯ: " + ", ".join(n.upper() for n in names)
