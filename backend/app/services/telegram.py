"""Linking a Telegram chat to an account (SPEC 11). The bot process calls these functions."""

import secrets

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.i18n.messages import bot_text
from app.models import Order, OrderStatus, User
from app.redis_client import get_redis
from app.schemas.notifications import TelegramLinkCode

CODE_TTL_SECONDS = 600
ACTIVE = (OrderStatus.pending_payment, OrderStatus.paid, OrderStatus.cooking, OrderStatus.ready)


def _key(code: str) -> str:
    return f"tg:link:{code}"


def create_link_code(user: User) -> TelegramLinkCode:
    redis = get_redis()
    while True:
        code = f"{secrets.randbelow(1_000_000):06d}"
        if redis.set(_key(code), user.id, ex=CODE_TTL_SECONDS, nx=True):
            break
    username = get_settings().telegram_bot_username or None
    return TelegramLinkCode(
        code=code,
        expires_in=CODE_TTL_SECONDS,
        bot_username=username,
        deep_link=f"https://t.me/{username}?start={code}" if username else None,
    )


def link_chat(db: Session, code: str, chat_id: int) -> User | None:
    """One-time: the code is gone after the first use or after 10 minutes."""
    raw = get_redis().getdel(_key(code.strip()))
    if raw is None:
        return None
    user = db.get(User, int(raw))
    if user is None or not user.is_active:
        return None
    # A chat belongs to one account: moving it frees the previous one.
    db.execute(
        update(User)
        .where(User.telegram_chat_id == chat_id, User.id != user.id)
        .values(telegram_chat_id=None)
    )
    user.telegram_chat_id = chat_id
    db.commit()
    return user


def user_by_chat(db: Session, chat_id: int) -> User | None:
    return db.scalar(select(User).where(User.telegram_chat_id == chat_id))


def unlink_chat(db: Session, chat_id: int) -> bool:
    user = user_by_chat(db, chat_id)
    if user is None:
        return False
    user.telegram_chat_id = None
    db.commit()
    return True


def unlink_user(db: Session, user: User) -> None:
    user.telegram_chat_id = None
    db.commit()


def handle_command(db: Session, chat_id: int, text: str) -> str:
    """The bot's whole logic as plain text in, text out, so it is testable without Telegram."""
    command, _, arg = (text or "").strip().partition(" ")
    command = command.split("@")[0].lower()
    user = user_by_chat(db, chat_id)
    lang = user.preferred_language if user else "ru"
    if command == "/start":
        if not arg:
            return bot_text("linked_already" if user else "start_help", lang)
        linked = link_chat(db, arg, chat_id)
        if linked is None:
            return bot_text("bad_code", lang)
        return bot_text("linked", linked.preferred_language, name=linked.full_name)
    if user is None:
        return bot_text("not_linked", lang)
    if command == "/orders":
        orders = db.scalars(
            select(Order)
            .where(Order.user_id == user.id, Order.status.in_(ACTIVE))
            .order_by(Order.created_at.desc())
            .limit(10)
        ).all()
        if not orders:
            return bot_text("no_orders", lang)
        lines = [bot_text("orders_title", lang)]
        for order in orders:
            slot = order.pickup_slot.starts_at.strftime("%H:%M") if order.pickup_slot else ""
            status = bot_text(f"status_{order.status.value}", lang)
            shelf = bot_text("shelf", lang, shelf=order.pickup_shelf) if order.pickup_shelf else ""
            lines.append(f"{order.order_number} · {slot} · {status}{shelf}")
        return "\n".join(lines)
    if command == "/stop":
        unlink_chat(db, chat_id)
        return bot_text("stopped", lang)
    return bot_text("help", lang)
