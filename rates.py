"""
KeyRush Currency Rates
──────────────────────
Живой курс валют (сколько рублей стоит 1 USD / 1 UAH), с сайта ЦБ РФ.

Внутри бота ВСЕ суммы (баланс пользователя, цена кейса, себестоимость и
рыночная стоимость приза, цена продажи ключа и т.д.) всегда хранятся и
считаются в рублях — это единственный источник правды. Этот модуль НИЧЕГО
не меняет во внутренней логике, он только:
  1) конвертирует рублёвую сумму в валюту пользователя — для показа на
     экране (display_amount / rub_to_currency);
  2) конвертирует сумму, введённую пользователем в его валюте, обратно
     в рубли — когда он вводит сумму пополнения (currency_to_rub).

Курс кэшируется на cfg.CURRENCY_RATE_TTL секунд, чтобы не ходить во внешний
API на каждое открытие меню. Если ЦБ недоступен — используется последний
известный курс, а если его тоже нет — cfg.FALLBACK_RATES.
"""
import ssl
import time
import asyncio
import logging

import aiohttp
import certifi

from config import cfg

log = logging.getLogger(__name__)

_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
_CBR_URL = "https://www.cbr-xml-daily.ru/daily_json.js"

# Кэш в памяти процесса: {"rates": {"USD": 90.1, "UAH": 2.3}, "fetched_at": ts}
_cache = {"rates": dict(cfg.FALLBACK_RATES), "fetched_at": 0.0}
_lock = asyncio.Lock()


async def _fetch_live_rates() -> dict:
    """Тянет курсы с ЦБ РФ. Значение уже приведено к 1 единице валюты
    (у ЦБ некоторые валюты котируются за Nominal > 1 единицу)."""
    timeout = aiohttp.ClientTimeout(total=10)
    connector = aiohttp.TCPConnector(ssl=_SSL_CONTEXT)
    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        async with session.get(_CBR_URL) as resp:
            data = await resp.json(content_type=None)

    valute = data["Valute"]
    return {
        "USD": float(valute["USD"]["Value"]) / float(valute["USD"].get("Nominal", 1)),
        "UAH": float(valute["UAH"]["Value"]) / float(valute["UAH"].get("Nominal", 1)),
    }


async def get_rates() -> dict:
    """Возвращает {"USD": <RUB за 1 USD>, "UAH": <RUB за 1 UAH>}.
    Обновляет кэш, если он устарел; при ошибке сети — отдаёт последний
    известный курс (или FALLBACK_RATES, если ещё ни разу не получилось)."""
    if time.time() - _cache["fetched_at"] < cfg.CURRENCY_RATE_TTL:
        return _cache["rates"]

    async with _lock:
        # Пока ждали лок, кэш мог обновить другой обработчик — перепроверяем.
        if time.time() - _cache["fetched_at"] < cfg.CURRENCY_RATE_TTL:
            return _cache["rates"]
        try:
            rates = await _fetch_live_rates()
            _cache["rates"] = rates
            _cache["fetched_at"] = time.time()
        except Exception as e:
            log.warning(f"Не удалось обновить курс валют с ЦБ РФ, использую прошлый курс: {e}")
            # fetched_at намеренно не трогаем, чтобы попытка повторилась
            # на следующем же запросе, а не через полный TTL.

    return _cache["rates"]


async def rub_to_currency(amount_rub: float, currency: str) -> float:
    """Рубли -> валюта пользователя (для отображения)."""
    if currency == "RUB" or not amount_rub:
        return amount_rub
    rates = await get_rates()
    rate = rates.get(currency)
    if not rate:
        return amount_rub
    return amount_rub / rate


async def currency_to_rub(amount, currency: str) -> float:
    """Валюта пользователя -> рубли (когда пользователь ВВОДИТ сумму,
    например при пополнении баланса)."""
    if currency == "RUB" or not amount:
        return amount
    rates = await get_rates()
    rate = rates.get(currency)
    if not rate:
        return amount
    return amount * rate


def _format_number(value: float, currency: str) -> str:
    if currency == "RUB":
        return str(round(value))
    rounded = round(value, 2)
    if rounded == int(rounded):
        return str(int(rounded))
    return f"{rounded:.2f}".rstrip("0").rstrip(".")


async def display_amount(amount_rub: float, currency: str) -> str:
    """Готовая строка суммы в валюте пользователя (без символа валюты) —
    то, что нужно подставлять в шаблоны локализации вместо голого RUB."""
    converted = await rub_to_currency(amount_rub, currency)
    return _format_number(converted, currency)
