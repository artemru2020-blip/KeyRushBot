"""
KeyRush Payment Handlers
CryptoBot + YooKassa + кастомная сумма + бонусы + i18n
"""
import math
import ssl
import time
import uuid
import logging
import aiohttp
import certifi
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, PreCheckoutQuery, LabeledPrice
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from config import cfg
from database import (
    update_user_balance, get_or_create_user, add_points,
    get_user_language, get_user_currency,
    create_pending_deposit, claim_deposit_credit,
    get_user_active_promo, set_user_active_promo,
    log_promo_usage, increment_promo_usage
)
from services.i18n import t, get_currency_symbol
from services.rates import display_amount, currency_to_rub, rub_to_currency
from services.adminlog import notify_admins, user_ref
from services.streamers import process_streamer_purchase
from keyboards import deposit_kb, deposit_pay_kb, cancel_kb
from states import DepositCustom

router = Router()
log = logging.getLogger(__name__)

CRYPTO_BOT_API = "https://pay.crypt.bot/api/"

# Явный SSL-контекст на certifi — подстраховка от CERTIFICATE_VERIFY_FAILED
# на macOS-сборках Python, где системные сертификаты не подхватываются сами.
_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())


async def safe_edit(callback: CallbackQuery, text: str, reply_markup=None, parse_mode="HTML"):
    # Сообщение может быть медиа (например, видео из /start) — его нельзя
    # редактировать через edit_text, только через edit_caption с лимитом
    # 1024 символа. Проще и надёжнее удалить его и прислать новое текстовое.
    if callback.message.text is None:
        try:
            await callback.message.delete()
        except TelegramBadRequest:
            pass
        await callback.message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
        return
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await callback.answer()
        else:
            raise


async def crypto_api_request(method: str, payload: dict = None) -> dict:
    headers = {"Crypto-Pay-API-Token": cfg.CRYPTO_BOT_TOKEN}
    timeout = aiohttp.ClientTimeout(total=15)
    connector = aiohttp.TCPConnector(ssl=_SSL_CONTEXT)
    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        url = f"{CRYPTO_BOT_API}{method}"
        if payload:
            async with session.post(url, headers=headers, json=payload) as resp:
                return await resp.json()
        else:
            async with session.get(url, headers=headers) as resp:
                return await resp.json()


async def _calc_bonus_points_and_consume_promo(user_id: int, amount: int) -> int:
    """
    Считает баллы к начислению за пополнение: баллы = полная сумма пополнения
    + 25% сверху (закинул 100 — получи 125 баллов). Если у пользователя
    активирован промокод на скидку к пополнению — его процент добавляется
    к базовым 25%, и промокод сразу помечается использованным (само
    начисление уже "заморожено" в bonus_points ожидающего депозита).
    """
    rate = cfg.BONUS_DEPOSIT_RATE
    promo = await get_user_active_promo(user_id)
    used_promo = None
    if promo and promo['promo_type'] == 'deposit':
        rate += promo['discount_percent'] / 100
        used_promo = promo

    bonus_points = amount + math.ceil(amount * rate)

    if used_promo:
        await log_promo_usage(used_promo['promo_id'], user_id)
        await increment_promo_usage(used_promo['promo_id'])
        await set_user_active_promo(user_id, None)

    return bonus_points


_bot_username_cache = None


async def _get_bot_deep_link(bot: Bot = None) -> str:
    """Возвращает реальную t.me-ссылку на этого бота (с кэшированием),
    вместо захардкоженного и вероятно неверного 'KeyRushBot'."""
    global _bot_username_cache
    if _bot_username_cache:
        return f"https://t.me/{_bot_username_cache}"
    if bot is not None:
        try:
            me = await bot.get_me()
            _bot_username_cache = me.username
            return f"https://t.me/{_bot_username_cache}"
        except Exception:
            log.exception("Не удалось получить username бота через get_me()")
    return "https://t.me/KeyRushBot"


# ─── Меню пополнения ─────────────────────────────────────

@router.callback_query(F.data == "menu_deposit")
async def menu_deposit(callback: CallbackQuery):
    user = await get_or_create_user(callback.from_user.id)
    lang = user.get('language', cfg.DEFAULT_LANG)
    cur = user.get('currency', cfg.DEFAULT_CURRENCY)
    sym = get_currency_symbol(cur)

    min_display = await display_amount(cfg.MIN_DEPOSIT_RUB, cur)
    await safe_edit(callback,
        t(lang, 'deposit', currency=sym, min=min_display),
        reply_markup=deposit_kb(lang),
        parse_mode="HTML"
    )
    await callback.answer()


# ─── CryptoBot ───────────────────────────────────────────

@router.callback_query(F.data == "deposit:crypto")
async def deposit_crypto(callback: CallbackQuery, state: FSMContext):
    user = await get_or_create_user(callback.from_user.id)
    lang = user.get('language', cfg.DEFAULT_LANG)
    cur = user.get('currency', cfg.DEFAULT_CURRENCY)
    sym = get_currency_symbol(cur)

    min_display = await display_amount(cfg.MIN_DEPOSIT_RUB, cur)
    await state.set_state(DepositCustom.crypto_amount)
    await safe_edit(callback,
        t(lang, 'enter_amount', currency=sym, min=min_display),
        reply_markup=cancel_kb("menu_deposit", lang),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(DepositCustom.crypto_amount)
async def deposit_crypto_amount(message: Message, state: FSMContext):
    user = await get_or_create_user(message.from_user.id)
    lang = user.get('language', cfg.DEFAULT_LANG)
    cur = user.get('currency', cfg.DEFAULT_CURRENCY)
    sym = get_currency_symbol(cur)

    try:
        amount = float(message.text.strip().replace(",", "."))
    except ValueError:
        await message.answer("❌ Введи число!")
        return

    # Сумма, введённая пользователем, — в его выбранной валюте (₽/₴/$).
    # Конвертируем в рубли по текущему курсу — именно в рублях у нас
    # хранится баланс и всё остальное внутри бота.
    amount_rub = round(await currency_to_rub(amount, cur))

    if amount_rub < cfg.MIN_DEPOSIT_RUB:
        min_display = await display_amount(cfg.MIN_DEPOSIT_RUB, cur)
        await message.answer(t(lang, 'min_deposit', currency=sym, min=min_display))
        return

    await state.clear()

    bonus_points = await _calc_bonus_points_and_consume_promo(message.from_user.id, amount_rub)

    # Конвертируем рубли → USDT по текущему курсу USD.
    usdt_amount = round(await rub_to_currency(amount_rub, "USD"), 2)

    payload = {
        "asset": "USDT",
        "amount": str(usdt_amount),
        "description": f"KeyRush пополнение на {amount}{sym}",
        "hidden_message": f"Спасибо за пополнение! +{bonus_points} бонусных баллов 🍀",
        # ВАЖНО: paid_btn_name у CryptoBot — это НЕ произвольный текст, а один из
        # фиксированных enum-значений API: viewItem / openChannel / openBot / callback.
        # "Open Bot" (с заглавных, с пробелом) API отклоняет как невалидное значение —
        # именно это и было причиной "Unknown error" ниже.
        "paid_btn_name": "openBot",
        "paid_btn_url": await _get_bot_deep_link(message.bot),
        "payload": f"user_{message.from_user.id}_amount_{amount}",
        "expires_in": 3600
    }

    try:
        result = await crypto_api_request("createInvoice", payload)
    except Exception as e:
        log.exception("CryptoBot createInvoice request failed")
        await message.answer(
            f"❌ Не удалось связаться с CryptoBot: {e}\n\n"
            f"Проверь токен в config.py и интернет-соединение. "
            f"Если ошибка про SSL-сертификат — на macOS помогает "
            f"'pip install --upgrade certifi' и перезапуск бота."
        )
        return

    if not result.get("ok"):
        # error у CryptoBot может прийти и строкой, и объектом {"code":..,"name":..} —
        # раньше код искал только result["error"]["message"] и почти всегда падал
        # в "Unknown error", даже когда реальная причина была в теле ответа.
        error_obj = result.get("error")
        if isinstance(error_obj, dict):
            error_msg = (
                error_obj.get("message")
                or error_obj.get("name")
                or str(error_obj)
            )
        elif error_obj:
            error_msg = str(error_obj)
        else:
            error_msg = str(result)
        log.warning(f"CryptoBot createInvoice error: {result}")
        await message.answer(f"❌ Ошибка создания счёта: {error_msg}")
        return

    invoice = result["result"]
    pay_url = invoice.get("bot_invoice_url") or invoice.get("pay_url")
    invoice_id = invoice["invoice_id"]

    # Регистрируем депозит как "pending" ДО показа кнопки проверки — чтобы при
    # реальной оплате точно знать, какую сумму/бонус зачислить и не доверять
    # клиентским данным из callback_data.
    await create_pending_deposit(
        user_id=message.from_user.id,
        provider="crypto",
        provider_ref=str(invoice_id),
        amount=amount_rub,
        bonus_points=bonus_points,
    )

    await message.answer(
        f"₿ <b>Счёт создан</b>\n\n"
        f"Сумма: <b>{amount}{sym}</b> (~{usdt_amount} USDT)\n"
        f"⭐ Бонусных баллов: <b>+{bonus_points}</b>\n"
        f"ID счёта: <code>{invoice_id}</code>\n\n"
        f"Нажми кнопку ниже для оплаты, затем — <b>✅ Я оплатил</b>",
        reply_markup=deposit_pay_kb("crypto", str(invoice_id), pay_url, lang),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("deposit_check:crypto:"))
async def deposit_crypto_check(callback: CallbackQuery):
    invoice_id = callback.data.split(":", 2)[2]

    user = await get_or_create_user(callback.from_user.id)
    lang = user.get('language', cfg.DEFAULT_LANG)
    cur = user.get('currency', cfg.DEFAULT_CURRENCY)
    sym = get_currency_symbol(cur)

    # Реально спрашиваем у CryptoBot статус ЭТОГО счета, а не верим кнопке на слово.
    try:
        result = await crypto_api_request("getInvoices", {"invoice_ids": invoice_id})
    except Exception:
        log.exception("CryptoBot getInvoices request failed")
        await callback.answer("❌ Не удалось проверить статус оплаты. Попробуй ещё раз чуть позже.", show_alert=True)
        return

    if not result.get("ok"):
        await callback.answer("❌ Счёт не найден у CryptoBot.", show_alert=True)
        return

    items = (result.get("result") or {}).get("items") or []
    invoice = next((it for it in items if str(it.get("invoice_id")) == str(invoice_id)), None)
    if not invoice or invoice.get("status") != "paid":
        await callback.answer("⏳ Оплата ещё не поступила. Попробуй проверить чуть позже.", show_alert=True)
        return

    # Атомарно помечаем депозит зачисленным — если это уже сделано (повторное
    # нажатие, гонка), claim_deposit_credit вернёт None и баланс не тронется повторно.
    deposit = await claim_deposit_credit("crypto", invoice_id)
    if not deposit:
        await callback.answer("✅ Этот депозит уже был зачислен ранее.", show_alert=True)
        return

    amount = deposit["amount"]  # в рублях
    bonus_points = deposit["bonus_points"]

    await update_user_balance(callback.from_user.id, amount)
    await add_points(callback.from_user.id, bonus_points)
    await process_streamer_purchase(callback.bot, callback.from_user.id, amount, source='deposit')

    await notify_admins(
        callback.bot,
        f"💰 <b>Пополнение баланса</b>\n"
        f"👤 {user_ref(callback.from_user.id, callback.from_user.username, callback.from_user.full_name)}\n"
        f"💳 Способ: ₿ CryptoBot\n"
        f"➕ Сумма: <b>{amount}₽</b> | ⭐ Бонус: {bonus_points} баллов"
    )

    amount_display = await display_amount(amount, cur)
    await safe_edit(callback,
        t(lang, 'deposit_success', amount=amount_display, currency=sym, points=bonus_points),
        reply_markup=cancel_kb("main_menu", lang),
        parse_mode="HTML"
    )
    await callback.answer(f"+{amount_display}{sym} и +{bonus_points} баллов! 💰")


# ─── YooKassa ────────────────────────────────────────────

@router.callback_query(F.data == "deposit:yookassa")
async def deposit_yookassa(callback: CallbackQuery, state: FSMContext):
    user = await get_or_create_user(callback.from_user.id)
    lang = user.get('language', cfg.DEFAULT_LANG)
    cur = user.get('currency', cfg.DEFAULT_CURRENCY)
    sym = get_currency_symbol(cur)

    if not cfg.YOOKASSA_SHOP_ID or not cfg.YOOKASSA_SECRET_KEY:
        await safe_edit(callback,
            "💳 <b>YooKassa</b>\n\n"
            "⚠️ Платёжная система временно недоступна.",
            reply_markup=cancel_kb("menu_deposit", lang),
            parse_mode="HTML"
        )
        await callback.answer()
        return

    min_display = await display_amount(cfg.MIN_DEPOSIT_RUB, cur)
    await state.set_state(DepositCustom.yookassa_amount)
    await safe_edit(callback,
        t(lang, 'enter_amount', currency=sym, min=min_display),
        reply_markup=cancel_kb("menu_deposit", lang),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(DepositCustom.yookassa_amount)
async def deposit_yookassa_amount(message: Message, state: FSMContext):
    user = await get_or_create_user(message.from_user.id)
    lang = user.get('language', cfg.DEFAULT_LANG)
    cur = user.get('currency', cfg.DEFAULT_CURRENCY)
    sym = get_currency_symbol(cur)

    try:
        amount = float(message.text.strip().replace(",", "."))
    except ValueError:
        await message.answer("❌ Введи число!")
        return

    # Сумма введена в валюте пользователя — переводим в рубли по текущему курсу.
    amount_rub = round(await currency_to_rub(amount, cur))

    if amount_rub < cfg.MIN_DEPOSIT_RUB:
        min_display = await display_amount(cfg.MIN_DEPOSIT_RUB, cur)
        await message.answer(t(lang, 'min_deposit', currency=sym, min=min_display))
        return

    await state.clear()
    bonus_points = await _calc_bonus_points_and_consume_promo(message.from_user.id, amount_rub)

    try:
        from yookassa import Configuration, Payment
        Configuration.account_id = cfg.YOOKASSA_SHOP_ID
        Configuration.secret_key = cfg.YOOKASSA_SECRET_KEY

        # ВАЖНО: магазин ЮKassa обычно подключен на конкретную валюту (в данном
        # случае — рубли). Если у пользователя выбрана другая валюта интерфейса
        # (UAH/USD), отправка её в поле amount.currency приведёт к ошибке на
        # стороне ЮKassa ("Currency not supported" и т.п.), хотя баланс у нас
        # внутренний и всегда в рублях. Поэтому здесь всегда используем RUB
        # (уже сконвертированную сумму amount_rub), а cur/sym — только для
        # отображения текста пользователю.
        idempotence_key = f"keyrush_{message.from_user.id}_{amount_rub}_{int(time.time())}"
        payment = Payment.create({
            "amount": {
                "value": f"{amount_rub}.00",
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": await _get_bot_deep_link(message.bot)
            },
            "capture": True,
            "description": f"KeyRush пополнение на {amount}{sym}",
            "metadata": {
                "user_id": message.from_user.id,
                "amount": amount_rub,
                "bonus_points": bonus_points
            }
        }, idempotence_key)

        confirmation_url = payment.confirmation.confirmation_url

        await create_pending_deposit(
            user_id=message.from_user.id,
            provider="yookassa",
            provider_ref=str(payment.id),
            amount=amount_rub,
            bonus_points=bonus_points,
        )

        await message.answer(
            f"💳 <b>YooKassa</b>\n\n"
            f"Сумма: <b>{amount}{sym}</b>\n"
            f"⭐ Бонусных баллов: <b>+{bonus_points}</b>\n\n"
            f"Нажми кнопку для оплаты:",
            reply_markup=deposit_pay_kb("yookassa", str(payment.id), confirmation_url, lang),
            parse_mode="HTML"
        )

    except Exception as e:
        log.exception("YooKassa payment creation failed")
        # SDK ЮKassa часто заворачивает реальную причину в структуру ApiError:
        # у e могут быть поля .code / .description / .parameter — а plain str(e)
        # нередко даёт малоинформативную строку. Достаём всё, что есть.
        details = []
        for attr in ("code", "description", "parameter", "type"):
            value = getattr(e, attr, None)
            if value:
                details.append(f"{attr}: {value}")
        error_text = str(e) or "Unknown error"
        if details:
            error_text += " (" + ", ".join(details) + ")"
        await message.answer(
            f"❌ Ошибка YooKassa: {error_text}\n\n"
            f"Попробуй CryptoBot или обратись к администратору.",
            reply_markup=cancel_kb("menu_deposit", lang),
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("deposit_check:yookassa:"))
async def deposit_yookassa_check(callback: CallbackQuery):
    payment_id = callback.data.split(":", 2)[2]

    user = await get_or_create_user(callback.from_user.id)
    lang = user.get('language', cfg.DEFAULT_LANG)
    cur = user.get('currency', cfg.DEFAULT_CURRENCY)
    sym = get_currency_symbol(cur)

    # Реально спрашиваем у ЮKassa статус ЭТОГО платежа, а не верим кнопке на слово.
    try:
        from yookassa import Configuration, Payment
        Configuration.account_id = cfg.YOOKASSA_SHOP_ID
        Configuration.secret_key = cfg.YOOKASSA_SECRET_KEY
        payment = Payment.find_one(payment_id)
    except Exception:
        log.exception("YooKassa Payment.find_one failed")
        await callback.answer("❌ Не удалось проверить статус оплаты. Попробуй ещё раз чуть позже.", show_alert=True)
        return

    if payment.status != "succeeded":
        await callback.answer("⏳ Оплата ещё не поступила. Попробуй проверить чуть позже.", show_alert=True)
        return

    # Атомарно помечаем депозит зачисленным — повторное нажатие/гонка не приведёт
    # к повторному начислению баланса.
    deposit = await claim_deposit_credit("yookassa", payment_id)
    if not deposit:
        await callback.answer("✅ Этот депозит уже был зачислен ранее.", show_alert=True)
        return

    amount = deposit["amount"]  # в рублях
    bonus_points = deposit["bonus_points"]

    await update_user_balance(callback.from_user.id, amount)
    await add_points(callback.from_user.id, bonus_points)
    await process_streamer_purchase(callback.bot, callback.from_user.id, amount, source='deposit')

    await notify_admins(
        callback.bot,
        f"💰 <b>Пополнение баланса</b>\n"
        f"👤 {user_ref(callback.from_user.id, callback.from_user.username, callback.from_user.full_name)}\n"
        f"💳 Способ: 💳 YooKassa\n"
        f"➕ Сумма: <b>{amount}₽</b> | ⭐ Бонус: {bonus_points} баллов"
    )

    amount_display = await display_amount(amount, cur)
    await safe_edit(callback,
        t(lang, 'deposit_success', amount=amount_display, currency=sym, points=bonus_points),
        reply_markup=cancel_kb("main_menu", lang),
        parse_mode="HTML"
    )
    await callback.answer(f"+{amount_display}{sym} и +{bonus_points} баллов! 💰")


# ─── Telegram Stars ───────────────────────────────────────

@router.callback_query(F.data == "deposit:stars")
async def deposit_stars(callback: CallbackQuery, state: FSMContext):
    user = await get_or_create_user(callback.from_user.id)
    lang = user.get('language', cfg.DEFAULT_LANG)

    await state.set_state(DepositCustom.stars_amount)
    await safe_edit(callback,
        t(lang, 'enter_stars_amount', min=cfg.MIN_STARS_DEPOSIT),
        reply_markup=cancel_kb("menu_deposit", lang),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(DepositCustom.stars_amount)
async def deposit_stars_amount(message: Message, state: FSMContext, bot: Bot):
    user = await get_or_create_user(message.from_user.id)
    lang = user.get('language', cfg.DEFAULT_LANG)

    try:
        stars = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введи целое число!")
        return

    if stars < cfg.MIN_STARS_DEPOSIT:
        await message.answer(t(lang, 'min_stars', min=cfg.MIN_STARS_DEPOSIT))
        return

    await state.clear()

    # Внутренний баланс всегда в рублях — конвертируем звёзды по курсу из конфига.
    amount_rub = round(stars * cfg.STARS_TO_RUB_RATE)
    bonus_points = await _calc_bonus_points_and_consume_promo(message.from_user.id, amount_rub)

    # Уникальный payload — по нему опознаём платёж в successful_payment
    # и атомарно защищаемся от повторного зачисления через claim_deposit_credit.
    payload = f"stars_{message.from_user.id}_{uuid.uuid4().hex}"

    await create_pending_deposit(
        user_id=message.from_user.id,
        provider="stars",
        provider_ref=payload,
        amount=amount_rub,
        bonus_points=bonus_points,
    )

    try:
        await bot.send_invoice(
            chat_id=message.chat.id,
            title=t(lang, 'stars_invoice_title'),
            description=t(lang, 'stars_invoice_desc', amount=amount_rub, points=bonus_points),
            payload=payload,
            provider_token="",  # для звёзд токен провайдера не нужен
            currency="XTR",
            prices=[LabeledPrice(label=t(lang, 'stars_invoice_title'), amount=stars)],
        )
    except Exception as e:
        log.exception("Не удалось выставить счёт в Telegram Stars")
        await message.answer(f"❌ Не удалось создать счёт: {e}")


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment(message: Message):
    sp = message.successful_payment

    if sp.currency == "XTR":
        # Оплата звёздами — сумма/бонус уже посчитаны и записаны в deposits
        # при выставлении счёта; здесь только атомарно подтверждаем зачисление.
        deposit = await claim_deposit_credit("stars", sp.invoice_payload)
        if not deposit:
            # Уже зачислено раньше (маловероятно, но подстраховка от дублей апдейтов)
            return
        amount = deposit["amount"]
        bonus_points = deposit["bonus_points"]
        provider_label = "⭐ Telegram Stars"
    else:
        # Универсальный обработчик для прочих встроенных Telegram-платежей,
        # если они когда-нибудь будут подключены (сумма в минимальных единицах).
        amount = sp.total_amount // 100
        bonus_points = amount + math.ceil(amount * cfg.BONUS_DEPOSIT_RATE)
        provider_label = sp.provider_payment_charge_id and "Telegram Payments" or "Telegram"

    await update_user_balance(message.from_user.id, amount)
    await add_points(message.from_user.id, bonus_points)
    await process_streamer_purchase(message.bot, message.from_user.id, amount, source='deposit')

    await notify_admins(
        message.bot,
        f"💰 <b>Пополнение баланса</b>\n"
        f"👤 {user_ref(message.from_user.id, message.from_user.username, message.from_user.full_name)}\n"
        f"💳 Способ: {provider_label}\n"
        f"➕ Сумма: <b>{amount}₽</b> | ⭐ Бонус: {bonus_points} баллов"
    )

    user = await get_or_create_user(message.from_user.id)
    lang = user.get('language', cfg.DEFAULT_LANG)
    cur = user.get('currency', cfg.DEFAULT_CURRENCY)
    sym = get_currency_symbol(cur)

    amount_display = await display_amount(amount, cur)
    await message.answer(
        t(lang, 'deposit_success', amount=amount_display, currency=sym, points=bonus_points),
        parse_mode="HTML"
    )
