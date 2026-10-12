"""python -m bot.main — the Telegram bot (aiogram 3, SPEC 11).

Commands go to `app.services.telegram.handle_command`; notifications queued by the API are
sent from the `outbox:telegram` Redis list. Without TELEGRAM_BOT_TOKEN the bot idles, so the
rest of the system runs as usual.
"""

import asyncio
import json
import logging

from aiogram import Bot, Dispatcher
from aiogram.types import Message
from redis.asyncio import Redis as AsyncRedis

from app.config import get_settings
from app.db import SessionLocal
from app.logs import setup_logging
from app.notifications.service import TELEGRAM_QUEUE
from app.services import telegram

log = logging.getLogger("bot")


def reply_for(chat_id: int, text: str) -> str:
    with SessionLocal() as db:
        return telegram.handle_command(db, chat_id, text)


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher()

    @dp.message()
    async def on_message(message: Message) -> None:
        answer = await asyncio.to_thread(reply_for, message.chat.id, message.text or "")
        await message.answer(answer)

    return dp


async def deliver_outbox(bot: Bot, redis: AsyncRedis) -> None:
    """Sends queued notifications one by one; a failed message is logged, not retried."""
    while True:
        item = await redis.blpop([TELEGRAM_QUEUE], timeout=5)
        if item is None:
            continue
        payload = json.loads(item[1])
        try:
            await bot.send_message(payload["chat_id"], payload["text"])
        except Exception:
            log.warning("telegram delivery to %s failed", payload.get("chat_id"), exc_info=True)


async def run() -> None:
    settings = get_settings()
    if not settings.telegram_bot_token:
        log.warning("TELEGRAM_BOT_TOKEN is empty: the bot is idle, the rest of the system works")
        while True:
            await asyncio.sleep(3600)
    bot = Bot(settings.telegram_bot_token)
    redis = AsyncRedis.from_url(settings.redis_url)
    outbox = asyncio.create_task(deliver_outbox(bot, redis))
    try:
        await build_dispatcher().start_polling(bot)
    finally:
        outbox.cancel()
        await redis.aclose()
        await bot.session.close()


def main() -> None:
    setup_logging(json=get_settings().app_env == "prod")
    asyncio.run(run())


if __name__ == "__main__":
    main()
