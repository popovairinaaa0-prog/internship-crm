"""Точка входа Telegram-ботов.

Запускает Dispatcher для студенческого бота (этап 6). Заглушка для второго
бота — менеджерского — добавится на этапе 8.
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher

from bot import settings as bot_settings
from bot.managers_bot.handlers import router as managers_router
from bot.student_bot.handlers import router as student_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
log = logging.getLogger("bot")


async def run_student_bot() -> None:
    token = bot_settings.ensure_student_bot()
    bot = Bot(token=token)
    dp = Dispatcher()
    dp.include_router(student_router)

    log.info("Студенческий бот стартует (long polling)")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


async def run_managers_bot() -> None:
    token = bot_settings.ensure_managers_bot()
    bot = Bot(token=token)
    dp = Dispatcher()
    dp.include_router(managers_router)

    log.info("Служебный бот стартует (long polling)")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


async def main() -> None:
    tasks: list[asyncio.Task] = []
    if bot_settings.STUDENT_BOT_TOKEN:
        tasks.append(asyncio.create_task(run_student_bot()))
    else:
        log.warning("STUDENT_BOT_TOKEN пустой — студенческий бот не запущен.")

    if bot_settings.MANAGERS_BOT_TOKEN:
        tasks.append(asyncio.create_task(run_managers_bot()))
    else:
        log.warning("MANAGERS_BOT_TOKEN пустой — служебный бот не запущен.")

    if not tasks:
        log.info("Ни один бот не запущен. Ставлю heartbeat в idle.")
        while True:
            await asyncio.sleep(3600)
    else:
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
