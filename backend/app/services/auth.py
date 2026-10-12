"""Registration, e-mail verification, login and refresh tokens (SPEC 7.1)."""

import hmac
import logging
import secrets
from datetime import timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app import ratelimit
from app.config import get_settings
from app.errors import ConflictError, DomainError, UnauthorizedError, ValidationError
from app.models import RefreshToken, StudentGroup, User, UserRole
from app.notifications.email import send_email
from app.redis_client import get_redis
from app.schemas.auth import RegisterRequest, TokenPair
from app.security import (
    create_access_token,
    hash_password,
    hash_token,
    new_refresh_token,
    verify_password,
)
from app.utils import time as clock

log = logging.getLogger(__name__)

CODE_ATTEMPTS = 5

EMAIL_TEXTS = {
    "ru": ("Код подтверждения", "Ваш код подтверждения: {code}. Он действует {minutes} минут."),
    "kk": ("Растау коды", "Растау кодыңыз: {code}. Ол {minutes} минут жарамды."),
    "en": ("Verification code", "Your verification code is {code}. It is valid for {minutes} min."),
}


def _code_key(user_id: int) -> str:
    return f"email_code:{user_id}"


def register(db: Session, data: RegisterRequest) -> tuple[User, bool]:
    settings = get_settings()
    email = data.email.lower()
    domain = email.rsplit("@", 1)[-1]
    if domain not in settings.email_domains:
        raise ValidationError(
            "email_domain_not_allowed",
            "Регистрация доступна только с университетской почты",
            {"allowed": sorted(settings.email_domains)},
        )
    role = UserRole(data.role)
    if role == UserRole.student:
        if data.group_id is None:
            raise ValidationError("group_required", "Студенту нужно выбрать группу")
        if db.get(StudentGroup, data.group_id) is None:
            raise ValidationError("group_not_found", "Группа не найдена")
    if db.scalar(select(User.id).where(func.lower(User.email) == email)):
        raise ConflictError("email_taken", "Этот e-mail уже зарегистрирован")

    user = User(
        email=email,
        full_name=data.full_name.strip(),
        password_hash=hash_password(data.password),
        role=role,
        group_id=data.group_id if role == UserRole.student else None,
        preferred_language=data.preferred_language,
    )
    db.add(user)
    db.commit()
    sent = send_verification_code(user)
    return user, sent


def send_verification_code(user: User) -> bool:
    settings = get_settings()
    code = f"{secrets.randbelow(1_000_000):06d}"
    get_redis().set(
        _code_key(user.id),
        f"{hash_token(code)}:0",
        ex=settings.verification_code_minutes * 60,
    )
    subject, body = EMAIL_TEXTS.get(user.preferred_language, EMAIL_TEXTS["ru"])
    return send_email(
        user.email, subject, body.format(code=code, minutes=settings.verification_code_minutes)
    )


def resend_code(db: Session, email: str) -> None:
    ratelimit.hit(f"resend:{email.lower()}", 3)
    user = db.scalar(select(User).where(func.lower(User.email) == email.lower()))
    # Do not reveal whether the address exists.
    if user is not None and user.email_verified_at is None:
        send_verification_code(user)


def verify_email(db: Session, email: str, code: str) -> User:
    user = db.scalar(select(User).where(func.lower(User.email) == email.lower()))
    if user is None:
        raise ValidationError("invalid_code", "Неверный или просроченный код")
    if user.email_verified_at is not None:
        return user
    redis = get_redis()
    stored = redis.get(_code_key(user.id))
    if stored is None:
        raise ValidationError("invalid_code", "Неверный или просроченный код")
    code_hash, attempts = stored.decode().rsplit(":", 1)
    if int(attempts) >= CODE_ATTEMPTS:
        redis.delete(_code_key(user.id))
        raise ValidationError("invalid_code", "Неверный или просроченный код")
    if not hmac.compare_digest(code_hash, hash_token(code)):
        ttl = redis.ttl(_code_key(user.id))
        redis.set(_code_key(user.id), f"{code_hash}:{int(attempts) + 1}", ex=max(int(ttl), 1))
        raise ValidationError("invalid_code", "Неверный или просроченный код")
    redis.delete(_code_key(user.id))
    user.email_verified_at = clock.now_utc()
    db.commit()
    return user


def _issue_tokens(db: Session, user: User) -> TokenPair:
    settings = get_settings()
    raw, token_hash = new_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=clock.now_utc() + timedelta(days=settings.refresh_token_days),
        )
    )
    db.commit()
    return TokenPair(
        access_token=create_access_token(user),
        refresh_token=raw,
        expires_in=settings.access_token_minutes * 60,
    )


def login(db: Session, email: str, password: str, client_ip: str) -> TokenPair:
    # Only failed attempts count: a whole campus can share one NAT address.
    limit = get_settings().login_attempts_per_minute
    ratelimit.check(f"login:{client_ip}", limit)
    user = db.scalar(select(User).where(func.lower(User.email) == email.lower()))
    if user is None or not verify_password(password, user.password_hash):
        ratelimit.hit(f"login:{client_ip}", limit + 1)
        raise UnauthorizedError("invalid_credentials", "Неверный e-mail или пароль")
    if not user.is_active:
        raise DomainError("user_blocked", "Аккаунт заблокирован", status_code=403)
    return _issue_tokens(db, user)


def refresh(db: Session, raw_token: str) -> TokenPair:
    now = clock.now_utc()
    # Revoke atomically so the same refresh token cannot be used twice.
    token = db.scalar(
        update(RefreshToken)
        .where(
            RefreshToken.token_hash == hash_token(raw_token),
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > now,
        )
        .values(revoked_at=now)
        .returning(RefreshToken)
    )
    if token is None:
        db.rollback()
        raise UnauthorizedError("invalid_refresh_token", "Сессия истекла, войдите снова")
    user = db.get(User, token.user_id)
    if user is None or not user.is_active:
        db.rollback()
        raise UnauthorizedError("invalid_refresh_token", "Сессия истекла, войдите снова")
    return _issue_tokens(db, user)


def logout(db: Session, raw_token: str) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.token_hash == hash_token(raw_token), RefreshToken.revoked_at.is_(None))
        .values(revoked_at=clock.now_utc())
    )
    db.commit()
