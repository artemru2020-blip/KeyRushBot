"""
KeyRush — начисление комиссии стримерам.

Вызывается после того, как деньги реально поступили (депозит зачислен)
или списаны за открытие кейса — единая точка для расчёта и начисления
партнёрской комиссии стримеру, если покупатель привязан к стримеру.
"""
import logging
from typing import Optional
from aiogram import Bot

from config import cfg
from database import (
    get_user, get_streamer_by_user, increment_streamer_customer_purchase,
    update_streamer_balance, log_streamer_earning, get_setting
)

log = logging.getLogger(__name__)


async def get_streamer_percents() -> tuple[float, float]:
    """Возвращает (процент с первой покупки, процент с последующих),
    с учётом значений, изменённых администратором из бота."""
    first = float(await get_setting("streamer_first_pct", str(cfg.STREAMER_FIRST_PURCHASE_PCT)))
    repeat = float(await get_setting("streamer_repeat_pct", str(cfg.STREAMER_REPEAT_PURCHASE_PCT)))
    return first, repeat


async def get_streamer_min_withdraw() -> int:
    return int(await get_setting("streamer_min_withdraw", str(cfg.STREAMER_MIN_WITHDRAW)))


async def process_streamer_purchase(bot: Optional[Bot], user_id: int, amount: int, source: str) -> None:
    """
    source: 'deposit' — пополнение баланса, 'case' — открытие кейса.
    amount: сумма покупки в рублях (сумма депозита или уплаченная за кейс цена).
    Ничего не делает, если пользователь не привязан ни к одному стримеру.
    """
    if amount <= 0:
        return

    user = await get_user(user_id)
    if not user or not user.get("attributed_streamer_id"):
        return

    streamer_id = user["attributed_streamer_id"]
    streamer = await get_streamer_by_user(streamer_id)
    if not streamer or not streamer.get("is_active"):
        return

    purchases_count = await increment_streamer_customer_purchase(streamer_id, user_id)
    first_pct, repeat_pct = await get_streamer_percents()
    percent = first_pct if purchases_count <= 1 else repeat_pct

    earned = round(amount * percent / 100)
    if earned <= 0:
        return

    await update_streamer_balance(streamer_id, earned)
    await log_streamer_earning(streamer_id, user_id, source, amount, percent, earned)

    if bot is not None:
        try:
            label = "пополнения" if source == "deposit" else "открытия кейса"
            await bot.send_message(
                streamer_id,
                f"💸 <b>Новое начисление!</b>\n\n"
                f"Ваш реферал сделал покупку ({label}) на <b>{amount}₽</b>.\n"
                f"Начислено: <b>+{earned}₽</b> ({percent}%)",
                parse_mode="HTML"
            )
        except Exception:
            log.debug("Не удалось уведомить стримера %s о начислении", streamer_id)
