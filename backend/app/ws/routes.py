"""WebSocket endpoints: `/ws/me` for a user's own orders and notifications,
`/ws/kitchen/{id}` for staff."""

import asyncio
import contextlib

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from redis.asyncio import Redis as AsyncRedis

from app.config import get_settings
from app.db import SessionLocal
from app.errors import DomainError
from app.models import User, UserRole
from app.security import user_from_token
from app.ws.events import kitchen_channel, notification_channel, user_channel

router = APIRouter()

KITCHEN_ROLES = {UserRole.cook, UserRole.cashier, UserRole.canteen_manager, UserRole.admin}
POLICY_VIOLATION = 1008


def _user_from_token(token: str | None) -> User | None:
    if not token:
        return None
    with SessionLocal() as db:
        try:
            user = user_from_token(db, token)
        except DomainError:
            return None
        db.expunge(user)
        return user


async def _relay(websocket: WebSocket, *channels: str) -> None:
    redis = AsyncRedis.from_url(get_settings().redis_url)
    pubsub = redis.pubsub()
    await pubsub.subscribe(*channels)
    await websocket.send_json({"type": "hello", "data": {}})

    async def forward() -> None:
        async for message in pubsub.listen():
            if message["type"] == "message":
                await websocket.send_text(message["data"].decode())

    async def watch_client() -> None:
        # Returns when the client goes away; incoming text is ignored (pings).
        with contextlib.suppress(WebSocketDisconnect):
            while True:
                await websocket.receive_text()

    tasks = [asyncio.create_task(forward()), asyncio.create_task(watch_client())]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in tasks:
            task.cancel()
        await pubsub.unsubscribe(*channels)
        await pubsub.aclose()
        await redis.aclose()


@router.websocket("/ws/me")
async def ws_me(websocket: WebSocket, token: str | None = None) -> None:
    user = _user_from_token(token)
    if user is None:
        await websocket.close(code=POLICY_VIOLATION)
        return
    await websocket.accept()
    await _relay(websocket, user_channel(user.id), notification_channel(user.id))


@router.websocket("/ws/kitchen/{canteen_id}")
async def ws_kitchen(websocket: WebSocket, canteen_id: int, token: str | None = None) -> None:
    user = _user_from_token(token)
    allowed = user is not None and user.role in KITCHEN_ROLES
    if allowed and user.role != UserRole.admin and user.canteen_id != canteen_id:
        allowed = False
    if not allowed:
        await websocket.close(code=POLICY_VIOLATION)
        return
    await websocket.accept()
    await _relay(websocket, kitchen_channel(canteen_id))
