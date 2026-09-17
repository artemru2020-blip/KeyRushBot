"""
KeyRush Bot Entry Point
"""
import os
import certifi

# ─── Фикс SSL-сертификатов на macOS (python.org-сборки Python не видят
#     системную связку сертификатов, из-за чего падают запросы к внешним
#     HTTPS API — CryptoBot, ЮКасса и т.д. с ошибкой CERTIFICATE_VERIFY_FAILED).
#     Должно быть выставлено ДО импорта aiohttp/requests/yookassa.
os.environ.setdefault("SSL_CERT_FILE", certifi.where())
os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import cfg
from database import init_db
from handlers import setup_routers

logging.basicConfig(level=logging.INFO)


async def main():
    await init_db()

    bot = Bot(
        token=cfg.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    dp.include_router(setup_routers())

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
