"""Discounts and order totals (SPEC 7.5, 7.10). Money is Decimal, rounded to whole tenge."""

from collections.abc import Iterable
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Promotion, PromotionStatus, PromotionType

TENGE = Decimal("1")


def round_tenge(amount: Decimal) -> Decimal:
    return amount.quantize(TENGE, rounding=ROUND_HALF_UP)


def discounted(price: Decimal, percent: int | None) -> Decimal:
    if not percent:
        return round_tenge(price)
    return round_tenge(price * (100 - percent) / 100)


def line_discount(unit_price: Decimal, quantity: int, percent: int | None) -> Decimal:
    """Per-unit rounding, so the line equals `price_now x quantity` shown in the menu."""
    if not percent:
        return Decimal("0")
    return (round_tenge(unit_price) - discounted(unit_price, percent)) * quantity


def _active(at: datetime):
    return (
        Promotion.status == PromotionStatus.active,
        Promotion.valid_from <= at,
        Promotion.valid_to >= at,
    )


def item_promotions(
    db: Session, menu_item_ids: Iterable[int], at: datetime
) -> dict[int, Promotion]:
    """The biggest active `leftover` promotion of each menu item."""
    ids = list(set(menu_item_ids))
    if not ids:
        return {}
    rows = db.scalars(
        select(Promotion).where(
            Promotion.type == PromotionType.leftover,
            Promotion.menu_item_id.in_(ids),
            *_active(at),
        )
    ).all()
    best: dict[int, Promotion] = {}
    for p in rows:
        assert p.menu_item_id is not None
        current = best.get(p.menu_item_id)
        if current is None or p.discount_percent > current.discount_percent:
            best[p.menu_item_id] = p
    return best


def slot_promotions(db: Session, slot_ids: Iterable[int], at: datetime) -> dict[int, Promotion]:
    """The biggest active `off_peak` promotion of each pickup slot."""
    ids = list(set(slot_ids))
    if not ids:
        return {}
    rows = db.scalars(
        select(Promotion).where(
            Promotion.type == PromotionType.off_peak,
            Promotion.pickup_slot_id.in_(ids),
            *_active(at),
        )
    ).all()
    best: dict[int, Promotion] = {}
    for p in rows:
        assert p.pickup_slot_id is not None
        current = best.get(p.pickup_slot_id)
        if current is None or p.discount_percent > current.discount_percent:
            best[p.pickup_slot_id] = p
    return best


def best_promotion(*candidates: Promotion | None) -> Promotion | None:
    """One discount per line: the biggest one wins (SPEC 7.10)."""
    present = [p for p in candidates if p is not None]
    if not present:
        return None
    return max(present, key=lambda p: (p.discount_percent, -p.id))
