"""Profile, allergies and health-data consent (SPEC 7.1, 7.3, 8.1)."""

from datetime import timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.errors import ValidationError
from app.models import Allergen, Order, OrderStatus, StudentGroup, User, UserAllergen, UserRole
from app.schemas.me import (
    AllergensPut,
    MeResponse,
    MeUpdate,
    MyAllergensResponse,
    UserAllergenOut,
)
from app.utils import time as clock


def no_show_count(db: Session, user_id: int, days: int = 30) -> int:
    since = clock.now_utc() - timedelta(days=days)
    return int(
        db.scalar(
            select(func.count(Order.id)).where(
                Order.user_id == user_id,
                Order.status == OrderStatus.no_show,
                Order.created_at >= since,
            )
        )
        or 0
    )


def profile(db: Session, user: User) -> MeResponse:
    return MeResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
        role=user.role,
        canteen_id=user.canteen_id,
        canteen_name=user.canteen.name if user.canteen else None,
        group_id=user.group_id,
        group_code=user.group.code if user.group else None,
        preferred_language=user.preferred_language,
        email_verified=user.email_verified_at is not None,
        health_data_consent_at=user.health_data_consent_at,
        loyalty_points=user.loyalty_points,
        telegram_linked=user.telegram_chat_id is not None,
        marketing_opt_out=user.marketing_opt_out,
        no_show_count_30d=no_show_count(db, user.id) if user.role in _CUSTOMERS else 0,
    )


_CUSTOMERS = (UserRole.student, UserRole.teacher)


def update_profile(db: Session, user: User, data: MeUpdate) -> User:
    if data.full_name is not None:
        user.full_name = data.full_name.strip()
    if data.preferred_language is not None:
        user.preferred_language = data.preferred_language
    if data.marketing_opt_out is not None:
        user.marketing_opt_out = data.marketing_opt_out
    if "group_id" in data.model_fields_set:
        if user.role != UserRole.student:
            raise ValidationError("group_only_for_students", "Группа есть только у студентов")
        if data.group_id is None or db.get(StudentGroup, data.group_id) is None:
            raise ValidationError("group_not_found", "Группа не найдена")
        user.group_id = data.group_id
    db.commit()
    db.refresh(user)
    return user


def my_allergens(db: Session, user: User) -> MyAllergensResponse:
    rows = db.execute(
        select(UserAllergen, Allergen)
        .join(Allergen, Allergen.id == UserAllergen.allergen_id)
        .where(UserAllergen.user_id == user.id)
        .order_by(Allergen.id)
    ).all()
    return MyAllergensResponse(
        health_data_consent_at=user.health_data_consent_at,
        allergens=[
            UserAllergenOut(
                allergen_id=a.id,
                code=a.code,
                name_ru=a.name_ru,
                name_kk=a.name_kk,
                severity=ua.severity,
            )
            for ua, a in rows
        ],
    )


def set_allergens(db: Session, user: User, data: AllergensPut) -> MyAllergensResponse:
    """Health data is stored only with consent (SPEC 7.3)."""
    if not data.consent:
        if data.allergens:
            raise ValidationError(
                "health_consent_required", "Нужно согласие на хранение данных о здоровье"
            )
        return revoke_consent(db, user)
    ids = [a.allergen_id for a in data.allergens]
    if len(set(ids)) != len(ids):
        raise ValidationError("duplicate_allergen", "Аллерген указан дважды")
    if ids:
        known = set(db.scalars(select(Allergen.id).where(Allergen.id.in_(ids))))
        if known != set(ids):
            raise ValidationError("allergen_not_found", "Неизвестный аллерген")
    if user.health_data_consent_at is None:
        user.health_data_consent_at = clock.now_utc()
    db.execute(delete(UserAllergen).where(UserAllergen.user_id == user.id))
    for a in data.allergens:
        db.add(UserAllergen(user_id=user.id, allergen_id=a.allergen_id, severity=a.severity))
    db.commit()
    return my_allergens(db, user)


def revoke_consent(db: Session, user: User) -> MyAllergensResponse:
    db.execute(delete(UserAllergen).where(UserAllergen.user_id == user.id))
    user.health_data_consent_at = None
    db.commit()
    return my_allergens(db, user)
