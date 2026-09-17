"""
KeyRush Admin Live-Log
Отправляет админам события бота (новый пользователь, открытие кейса,
пополнение баланса и т.д.) прямо в личный чат. Включается/выключается
из админ-панели.
"""
import logging
from aiogram import Bot

from config import cfg
from database import get_setting, set_setting

log = logging.getLogger(__name__)

_SETTING_KEY = "admin_log_enabled"


async def is_admin_log_enabled() -> bool:
    default = "1" if cfg.ADMIN_LOG_DEFAULT_ENABLED else "0"
    value = await get_setting(_SETTING_KEY, default)
    return value == "1"


async def set_admin_log_enabled(enabled: bool):
    await set_setting(_SETTING_KEY, "1" if enabled else "0")


async def notify_admins(bot: Bot, text: str):
    """Рассылает текст всем ID из cfg.ADMIN_IDS, если лог включён."""
    if not await is_admin_log_enabled():
        return
    for admin_id in cfg.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, parse_mode="HTML")
        except Exception:
            log.exception("Не удалось отправить лог-сообщение админу %s", admin_id)


def user_ref(user_id: int, username: str = None, full_name: str = None) -> str:
    """Короткая ссылка-описание пользователя для лог-сообщений."""
    name = full_name or "—"
    uname = f"@{username}" if username else "нет username"
    return f"{name} ({uname}) · <code>{user_id}</code>"
