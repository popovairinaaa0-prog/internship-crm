"""Точка входа Telegram-ботов.

Реальные хендлеры появятся на этапах 6 (студенческий бот) и 8 (служебный бот).
Пока — заглушка, чтобы docker-compose-сервис `bot` не падал.
"""

import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
log = logging.getLogger("bot")


async def main() -> None:
    log.info("Боты ещё не подключены. Заглушка работает.")
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
