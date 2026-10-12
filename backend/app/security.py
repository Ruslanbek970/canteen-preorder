"""Password hashing, JWT and role dependencies (SPEC 7.1, 12)."""

import hashlib
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import bcrypt
import jwt
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.errors import ForbiddenError, UnauthorizedError
from app.models import User, UserRole

ALGORITHM = "HS256"
STAFF_ROLES = (UserRole.cook, UserRole.cashier, UserRole.canteen_manager)
CUSTOMER_ROLES = (UserRole.student, UserRole.teacher)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def create_access_token(user: User) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user.id),
        "role": user.role.value,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(payload, settings.jwt_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, get_settings().jwt_key, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("token_expired", "Access token expired") from exc
    except jwt.PyJWTError as exc:
        raise UnauthorizedError("invalid_token", "Invalid access token") from exc
    if payload.get("type") != "access":
        raise UnauthorizedError("invalid_token", "Invalid access token")
    return payload


def new_refresh_token() -> tuple[str, str]:
    """Returns (raw token for the client, sha256 hash for the database)."""
    raw = secrets.token_urlsafe(48)
    return raw, hash_token(raw)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _bearer(request: Request) -> str | None:
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip() or None
    return None


def user_from_token(db: Session, token: str) -> User:
    payload = decode_access_token(token)
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise UnauthorizedError("invalid_token", "User is not active")
    return user


def get_current_user(request: Request, db: Annotated[Session, Depends(get_db)]) -> User:
    token = _bearer(request)
    if not token:
        raise UnauthorizedError("not_authenticated", "Authentication required")
    return user_from_token(db, token)


def get_optional_user(request: Request, db: Annotated[Session, Depends(get_db)]) -> User | None:
    token = _bearer(request)
    if not token:
        return None
    try:
        return user_from_token(db, token)
    except UnauthorizedError:
        return None


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_optional_user)]


def require_roles(*roles: UserRole) -> Callable[..., User]:
    """Dependency: the current user must have one of `roles` (SPEC 6)."""

    def dependency(user: CurrentUser) -> User:
        if user.role not in roles:
            raise ForbiddenError("forbidden", "Not allowed for your role")
        return user

    return dependency


def staff_canteen_id(user: User) -> int | None:
    """Staff see only their canteen; admins are not limited (None)."""
    if user.role in STAFF_ROLES:
        return user.canteen_id
    return None


def ensure_canteen_access(user: User, canteen_id: int) -> None:
    if user.role in STAFF_ROLES and user.canteen_id != canteen_id:
        raise ForbiddenError("foreign_canteen", "Access to another canteen is not allowed")
