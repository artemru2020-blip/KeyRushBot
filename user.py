"""
KeyRush User Handlers (i18n)
"""
import random
import math
import os
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from config import cfg
from database import (
    get_or_create_user, get_cases, get_case, get_case_prizes, get_user,
    can_take_bonus, log_bonus, add_points, get_last_bonus_time,
    add_to_inventory, get_user_inventory, sell_inventory_item,
    set_user_language, get_user_language, get_user_currency, set_user_currency,
    get_promocode_by_code, has_user_used_promo, set_user_active_promo,
    get_user_active_promo, log_promo_usage, increment_promo_usage,
    set_daily_top_win, set_user_attributed_streamer
)
from services.economy import EconomyEngine
from services.i18n import t, get_currency_symbol
from services.rates import display_amount
from services.adminlog import notify_admins, user_ref
from services.streamers import process_streamer_purchase
from keyboards import (
    main_menu_kb, cases_list_kb, case_confirm_kb, case_result_kb,
    bonus_kb, profile_kb, cancel_kb, inventory_kb, lang_kb
)
from states import PromoActivate

router = Router()


def _format_countdown(seconds: float) -> str:
    """Форматирует оставшееся время в виде ЧЧ:MM:СС."""
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


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


async def send_start_screen(target, text: str, lang: str, is_admin: bool):
    """
    Отправляет главный экран (видео + подпись + меню).
    target — объект с методами answer_video/answer: подходит и Message (из /start),
    и callback.message (при возврате в главное меню).
    """
    if os.path.isfile(cfg.START_VIDEO_PATH) and len(text) <= 1024:
        await target.answer_video(
            video=FSInputFile(cfg.START_VIDEO_PATH),
            caption=text,
            reply_markup=main_menu_kb(lang, is_admin),
            parse_mode="HTML"
        )
    else:
        if os.path.isfile(cfg.START_VIDEO_PATH):
            await target.answer_video(video=FSInputFile(cfg.START_VIDEO_PATH))
        await target.answer(text, reply_markup=main_menu_kb(lang, is_admin), parse_mode="HTML")


# ─── /start ──────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    user = await get_or_create_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.full_name
    )
    lang = user.get('language', cfg.DEFAULT_LANG)
    cur = user.get('currency', cfg.DEFAULT_CURRENCY)
    sym = get_currency_symbol(cur)

    is_admin = message.from_user.id in cfg.ADMIN_IDS

    if user.get('_is_new'):
        await notify_admins(
            bot,
            f"🆕 <b>Новый пользователь</b>\n"
            f"👤 {user_ref(message.from_user.id, message.from_user.username, message.from_user.full_name)}"
        )

        # ─── Реферальная ссылка: /start ref<user_id> ───
        parts = (message.text or "").split(maxsplit=1)
        if len(parts) > 1:
            payload = parts[1].strip()
            if payload.lower().startswith("ref") and payload[3:].isdigit():
                referrer_id = int(payload[3:])
                from handlers.referral import apply_referral
                await apply_referral(bot, message.from_user.id, referrer_id)
                user = await get_or_create_user(message.from_user.id)  # обновлённые баллы

    bal = await display_amount(user['balance_rub'], cur)
    text = (
        f"{t(lang, 'welcome')}\n\n"
        f"{t(lang, 'balance', balance=bal, currency=sym)}\n"
        f"{t(lang, 'points', points=user['points'], target=cfg.POINTS_FOR_PREMIUM_KEY)}\n"
        f"🎲 {t(lang, 'total_opens', count=user['total_opens'])}\n\n"
        f"{t(lang, 'support_link')}"
    )

    await send_start_screen(message, text, lang, is_admin)


@router.callback_query(F.data == "main_menu")
async def main_menu(callback: CallbackQuery, bot: Bot = None):
    user = await get_or_create_user(
        callback.from_user.id,
        callback.from_user.username,
        callback.from_user.full_name
    )
    lang = user.get('language', cfg.DEFAULT_LANG)
    cur = user.get('currency', cfg.DEFAULT_CURRENCY)
    sym = get_currency_symbol(cur)

    is_admin = callback.from_user.id in cfg.ADMIN_IDS

    bal = await display_amount(user['balance_rub'], cur)
    text = (
        f"🎰 <b>KeyRush</b> 🎰\n\n"
        f"{t(lang, 'balance', balance=bal, currency=sym)}\n"
        f"{t(lang, 'points', points=user['points'], target=cfg.POINTS_FOR_PREMIUM_KEY)}\n"
        f"🎲 {t(lang, 'total_opens', count=user['total_opens'])}\n\n"
        f"{t(lang, 'support_link')}"
    )

    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass
    await send_start_screen(callback.message, text, lang, is_admin)
    await callback.answer()


# ─── Language ────────────────────────────────────────────

@router.callback_query(F.data == "menu_lang")
async def menu_lang(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    lang = user.get('language', cfg.DEFAULT_LANG) if user else cfg.DEFAULT_LANG
    await safe_edit(callback,
        t(lang, 'choose_lang'),
        reply_markup=lang_kb(lang),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("lang:"))
async def set_lang(callback: CallbackQuery):
    new_lang = callback.data.split(":")[1]
    await set_user_language(callback.from_user.id, new_lang)
    # Валюта отображения переключается вместе с языком (ru→₽, ua→₴, en→$).
    # Раньше это поле не трогалось вообще, из-за чего символ валюты
    # оставался прежним независимо от выбранного языка.
    new_currency = cfg.LANG_CURRENCY.get(new_lang, cfg.DEFAULT_CURRENCY)
    await set_user_currency(callback.from_user.id, new_currency)
    await callback.answer(t(new_lang, 'lang_changed'), show_alert=True)
    await main_menu(callback, None)


# ─── Кейсы ───────────────────────────────────────────────

@router.callback_query(F.data == "menu_cases")
async def menu_cases(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    lang = user.get('language', cfg.DEFAULT_LANG) if user else cfg.DEFAULT_LANG

    cases = await get_cases(active_only=True)
    if not cases:
        await safe_edit(callback,
            t(lang, 'no_cases'),
            reply_markup=cancel_kb("main_menu", lang)
        )
        await callback.answer()
        return

    user = await get_user(callback.from_user.id)
    cur = user.get('currency', cfg.DEFAULT_CURRENCY) if user else cfg.DEFAULT_CURRENCY
    sym = get_currency_symbol(cur)

    # Кейсы всегда хранят цену в рублях — конвертируем только для показа.
    display_cases = []
    for c in cases:
        c2 = dict(c)
        c2['price'] = await display_amount(c['price'], cur)
        display_cases.append(c2)

    await safe_edit(callback,
        t(lang, 'choose_case'),
        reply_markup=cases_list_kb(display_cases, lang, sym),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("case_open:"))
async def case_open(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    lang = user.get('language', cfg.DEFAULT_LANG) if user else cfg.DEFAULT_LANG
    cur = user.get('currency', cfg.DEFAULT_CURRENCY) if user else cfg.DEFAULT_CURRENCY
    sym = get_currency_symbol(cur)

    case_id = int(callback.data.split(":")[1])
    case = await get_case(case_id)
    if not case:
        await callback.answer("Кейс не найден", show_alert=True)
        return

    prizes = await get_case_prizes(case_id)
    if not prizes:
        await callback.answer("В кейсе пока нет призов", show_alert=True)
        return

    price_display = await display_amount(case['price'], cur)
    text = f"🎲 <b>{case['name']}</b>\n"
    if case.get('description'):
        text += f"📝 {case['description']}\n"
    text += (
        f"{t(lang, 'case_price', price=price_display, currency=sym)}\n\n"
        f"Хочешь испытать удачу?"
    )

    kb = case_confirm_kb(case_id, price_display, lang, sym)
    image_url = case.get('image_url')

    if image_url:
        # Изображение кейса (file_id из Telegram или прямая ссылка) — отправляем
        # отдельным фото-сообщением с подписью, т.к. edit_text не умеет
        # превращать текстовое сообщение в медиа. Подпись ограничена 1024 символами.
        caption = text if len(text) <= 1024 else text[:1021] + "..."
        try:
            await callback.message.delete()
        except TelegramBadRequest:
            pass
        try:
            await callback.message.answer_photo(
                photo=image_url, caption=caption, reply_markup=kb, parse_mode="HTML"
            )
        except TelegramBadRequest:
            # Битый file_id/ссылка на изображение — не роняем сценарий, просто текстом
            await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    else:
        await safe_edit(callback, text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("case_confirm:"))
async def case_confirm(callback: CallbackQuery, bot: Bot):
    user = await get_user(callback.from_user.id)
    lang = user.get('language', cfg.DEFAULT_LANG) if user else cfg.DEFAULT_LANG
    cur = user.get('currency', cfg.DEFAULT_CURRENCY) if user else cfg.DEFAULT_CURRENCY
    sym = get_currency_symbol(cur)

    case_id = int(callback.data.split(":")[1])
    case = await get_case(case_id)
    user = await get_user(callback.from_user.id)

    if not case or not user:
        await callback.answer("Ошибка", show_alert=True)
        return

    # ─── Применяем активированный промокод на скидку открытия кейса ───
    price = case['price']
    promo = None
    active_promo = await get_user_active_promo(callback.from_user.id)
    if active_promo and active_promo['promo_type'] == 'case' and \
            (active_promo['case_id'] is None or active_promo['case_id'] == case_id):
        promo = active_promo
        price = max(0, round(price - price * promo['discount_percent'] / 100))

    if user['balance_rub'] < price:
        price_display = await display_amount(price, cur)
        await callback.answer(
            f"💳 Недостаточно средств! Нужно {price_display}{sym}",
            show_alert=True
        )
        return

    from database import update_user_balance
    await update_user_balance(callback.from_user.id, -price)

    await safe_edit(callback, t(lang, 'open_case'), parse_mode="HTML")

    try:
        result = await EconomyEngine.process_open(callback.from_user.id, case_id, price)
    except ValueError as e:
        await update_user_balance(callback.from_user.id, price)
        await safe_edit(callback,
            f"😕 Ошибка: {e}\nДеньги возвращены на баланс.",
            reply_markup=case_result_kb(lang),
            parse_mode="HTML"
        )
        await callback.answer()
        return

    if promo:
        # Промокод одноразовый — фиксируем использование и снимаем активацию.
        await log_promo_usage(promo['promo_id'], callback.from_user.id)
        await increment_promo_usage(promo['promo_id'])
        await set_user_active_promo(callback.from_user.id, None)

    # Комиссия стримеру, если этот пользователь привязан к чьему-то промокоду.
    await process_streamer_purchase(bot, callback.from_user.id, price, source='case')

    prize = result['prize']
    key = result['key']
    is_premium = result['is_premium']

    if is_premium:
        await set_daily_top_win(
            game_name=prize['game_name'],
            user_display=f"ID:{callback.from_user.id}",
            is_fake=0
        )

    sell_price = int(prize['cost_price'] * cfg.SELL_BACK_RATE)
    await add_to_inventory(
        user_id=callback.from_user.id,
        prize_id=prize['prize_id'],
        key_id=result.get('key_id', 0),
        game_name=prize['game_name'],
        steam_key=key,
        sell_price=sell_price
    )

    await notify_admins(
        bot,
        f"🎲 <b>Открытие кейса</b>\n"
        f"👤 {user_ref(callback.from_user.id, callback.from_user.username, callback.from_user.full_name)}\n"
        f"📦 Кейс: <b>{case['name']}</b> ({price}₽{' 🎟 промокод' if promo else ''})\n"
        f"🎮 Приз: <b>{prize['game_name']}</b> ({prize['rarity']})\n"
        f"🔑 Ключ: <code>{key}</code>"
    )

    rarity_emoji = {
        'common': '⚪',
        'uncommon': '🟢',
        'rare': '🔵',
        'epic': '🟣',
        'legendary': '🟡'
    }.get(prize['rarity'], '⚪')

    market_value_display = await display_amount(prize['market_value'], cur)
    sell_price_display = await display_amount(sell_price, cur)
    promo_line = ""
    if promo:
        old_display = await display_amount(case['price'], cur)
        new_display = await display_amount(price, cur)
        promo_line = t(lang, 'promo_case_applied', percent=promo['discount_percent'],
                       old=old_display, new=new_display, currency=sym) + chr(10)

    text = (
        f"{'🎉🎉🎉' if is_premium else '🎉'} {t(lang, 'you_won')} {'🎉🎉🎉' if is_premium else '🎉'}\n\n"
        f"{rarity_emoji} <b>{prize['game_name']}</b>\n"
        f"{t(lang, 'rarity', rarity=prize['rarity'].upper())}\n"
        f"{t(lang, 'market_value', value=market_value_display, currency=sym)}\n"
        f"{t(lang, 'sell_price', price=sell_price_display, currency=sym)}\n\n"
        f"{t(lang, 'your_key', key=key)}\n\n"
        f"Ключ сохранён в 📦 Инвентаре.\n"
        f"{promo_line}"
        f"{'💎 Это редкий выигрыш! Начислены бонусные баллы!' if is_premium else ''}"
    )

    await safe_edit(callback, text, reply_markup=case_result_kb(lang), parse_mode="HTML")
    await callback.answer(
        f"🎉 {prize['game_name']}!" if not is_premium else "💎 ЭПИЧЕСКИЙ ВЫИГРЫШ!",
        show_alert=is_premium
    )


# ─── Инвентарь ───────────────────────────────────────────

@router.callback_query(F.data == "menu_inventory")
async def menu_inventory(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    lang = user.get('language', cfg.DEFAULT_LANG) if user else cfg.DEFAULT_LANG
    cur = user.get('currency', cfg.DEFAULT_CURRENCY) if user else cfg.DEFAULT_CURRENCY
    sym = get_currency_symbol(cur)

    items = await get_user_inventory(callback.from_user.id)
    if not items:
        await safe_edit(callback,
            t(lang, 'inventory_empty'),
            reply_markup=cancel_kb("main_menu", lang)
        )
        await callback.answer()
        return

    display_items = []
    lines = []
    for i, item in enumerate(items):
        price_display = await display_amount(item['sell_price'], cur)
        lines.append(f"{i+1}. <b>{item['game_name']}</b> — {t(lang, 'sell_price', price=price_display, currency=sym)}")
        item2 = dict(item)
        item2['sell_price'] = price_display
        display_items.append(item2)

    text = t(lang, 'inventory', items="\n".join(lines))

    await safe_edit(callback, text, reply_markup=inventory_kb(display_items, lang, sym), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("sell_key:"))
async def sell_key(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    lang = user.get('language', cfg.DEFAULT_LANG) if user else cfg.DEFAULT_LANG
    cur = user.get('currency', cfg.DEFAULT_CURRENCY) if user else cfg.DEFAULT_CURRENCY
    sym = get_currency_symbol(cur)

    inv_id = int(callback.data.split(":")[1])
    item = await sell_inventory_item(inv_id, callback.from_user.id)

    if not item:
        await callback.answer("❌ Ключ не найден или уже продан", show_alert=True)
        return

    price_display = await display_amount(item['sell_price'], cur)
    await safe_edit(callback,
        t(lang, 'sold', game=item['game_name'], price=price_display, currency=sym),
        reply_markup=cancel_kb("main_menu", lang),
        parse_mode="HTML"
    )
    await callback.answer(f"+{price_display}{sym} 💰")


# ─── Профиль ─────────────────────────────────────────────

@router.callback_query(F.data == "menu_profile")
async def menu_profile(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    if not user:
        await callback.answer("Ошибка", show_alert=True)
        return

    lang = user.get('language', cfg.DEFAULT_LANG)
    cur = user.get('currency', cfg.DEFAULT_CURRENCY)
    sym = get_currency_symbol(cur)

    text = t(lang, 'profile',
        user_id=user['user_id'],
        balance=await display_amount(user['balance_rub'], cur),
        currency=sym,
        points=user['points'],
        target=cfg.POINTS_FOR_PREMIUM_KEY,
        opens=user['total_opens'],
        spent=user['total_spent']
    )

    await safe_edit(callback, text, reply_markup=profile_kb(lang), parse_mode="HTML")
    await callback.answer()


# ─── Ежедневный бонус ────────────────────────────────────

@router.callback_query(F.data == "menu_bonus")
async def menu_bonus(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    lang = user.get('language', cfg.DEFAULT_LANG) if user else cfg.DEFAULT_LANG

    can_take = await can_take_bonus(callback.from_user.id)

    text = t(lang, 'bonus',
        target=cfg.POINTS_FOR_PREMIUM_KEY,
        points=user['points'],
        remaining=max(0, cfg.POINTS_FOR_PREMIUM_KEY - user['points'])
    )

    if not can_take:
        last = await get_last_bonus_time(callback.from_user.id)
        if last:
            remaining_seconds = 20 * 3600 - (datetime.now() - last).total_seconds()
        else:
            remaining_seconds = 0
        text += "\n\n" + t(lang, 'bonus_cooldown', time=_format_countdown(remaining_seconds))

    await safe_edit(callback, text, reply_markup=bonus_kb(can_take, lang), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "bonus_take")
async def bonus_take(callback: CallbackQuery):
    can_take = await can_take_bonus(callback.from_user.id)
    if not can_take:
        await callback.answer("⏳ Бонус уже получен. Приходи позже!", show_alert=True)
        return

    points = random.randint(cfg.DAILY_BONUS_MIN, cfg.DAILY_BONUS_MAX)
    await add_points(callback.from_user.id, points)
    await log_bonus(callback.from_user.id, points)

    user = await get_user(callback.from_user.id)
    lang = user.get('language', cfg.DEFAULT_LANG) if user else cfg.DEFAULT_LANG

    text = t(lang, 'bonus_taken',
        points=points,
        total=user['points'],
        remaining=max(0, cfg.POINTS_FOR_PREMIUM_KEY - user['points'])
    )

    await safe_edit(callback, text, reply_markup=cancel_kb("main_menu", lang), parse_mode="HTML")
    await callback.answer(f"+{points} баллов! 🎁")


# ─── Обмен баллов ────────────────────────────────────────

@router.callback_query(F.data == "menu_redeem")
async def menu_redeem(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    if not user:
        await callback.answer("Ошибка", show_alert=True)
        return

    lang = user.get('language', cfg.DEFAULT_LANG)
    cur = user.get('currency', cfg.DEFAULT_CURRENCY)
    sym = get_currency_symbol(cur)

    if user['points'] >= cfg.POINTS_FOR_PREMIUM_KEY:
        from database import get_prizes, get_available_key, mark_key_used
        prizes = await get_prizes()
        premium = [p for p in prizes if p['rarity'] in ['epic', 'legendary'] and p['available_keys'] > 0]

        if not premium:
            await callback.answer(
                "😕 Сейчас нет доступных премиум-призов. Попробуй позже!",
                show_alert=True
            )
            return

        selected = random.choice(premium)
        key_row = await get_available_key(selected['prize_id'])
        if not key_row:
            await callback.answer("Ошибка выдачи приза", show_alert=True)
            return

        await add_points(callback.from_user.id, -cfg.POINTS_FOR_PREMIUM_KEY)
        await mark_key_used(key_row['key_id'], callback.from_user.id)

        sell_price = int(selected['cost_price'] * cfg.SELL_BACK_RATE)
        await add_to_inventory(
            user_id=callback.from_user.id,
            prize_id=selected['prize_id'],
            key_id=key_row['key_id'],
            game_name=selected['game_name'],
            steam_key=key_row['steam_key'],
            sell_price=sell_price
        )

        sell_price_display = await display_amount(sell_price, cur)
        text = (
            f"💎 <b>ПОЗДРАВЛЯЕМ!</b> 💎\n\n"
            f"Вы обменяли <b>{cfg.POINTS_FOR_PREMIUM_KEY:,}</b> баллов на ценный ключ!\n\n"
            f"🎮 <b>{selected['game_name']}</b>\n"
            f"🔑 <b>Ваш ключ:</b>\n"
            f"<code>{key_row['steam_key']}</code>\n"
            f"♻️ Можешь продать за {sell_price_display}{sym} в инвентаре"
        )

        await safe_edit(callback, text, reply_markup=cancel_kb("main_menu", lang), parse_mode="HTML")
        await callback.answer("💎 Премиум ключ получен!", show_alert=True)
    else:
        remaining = cfg.POINTS_FOR_PREMIUM_KEY - user['points']
        await callback.answer(
            f"⭐ Нужно ещё {remaining:,} баллов для обмена!",
            show_alert=True
        )


# ─── Промокоды ───────────────────────────────────────────

@router.callback_query(F.data == "menu_promo")
async def menu_promo(callback: CallbackQuery, state: FSMContext):
    user = await get_user(callback.from_user.id)
    lang = user.get('language', cfg.DEFAULT_LANG) if user else cfg.DEFAULT_LANG

    await state.set_state(PromoActivate.code)
    await safe_edit(callback,
        t(lang, 'promo_enter'),
        reply_markup=cancel_kb("main_menu", lang),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(PromoActivate.code)
async def promo_activate_code(message: Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    lang = user.get('language', cfg.DEFAULT_LANG) if user else cfg.DEFAULT_LANG

    await state.clear()

    promo = await get_promocode_by_code(message.text.strip())

    if (
        not promo
        or not promo['is_active']
        or (promo['max_uses'] is not None and promo['used_count'] >= promo['max_uses'])
    ):
        await message.answer(t(lang, 'promo_invalid'), reply_markup=cancel_kb("main_menu", lang), parse_mode="HTML")
        return

    if await has_user_used_promo(promo['promo_id'], message.from_user.id):
        await message.answer(t(lang, 'promo_already_used'), reply_markup=cancel_kb("main_menu", lang), parse_mode="HTML")
        return

    await set_user_active_promo(message.from_user.id, promo['promo_id'])

    # ─── Стримерский промокод: привязываем зрителя к стримеру навсегда,
    # чтобы стример получал комиссию со всех его будущих покупок ───
    if promo.get('streamer_owner_id'):
        await set_user_attributed_streamer(message.from_user.id, promo['streamer_owner_id'])

    if promo['promo_type'] == 'deposit':
        text = t(lang, 'promo_activated_deposit', percent=promo['discount_percent'])
    else:
        if promo['case_id']:
            case = await get_case(promo['case_id'])
            scope = t(lang, 'promo_scope_case', name=case['name'] if case else '?')
        else:
            scope = t(lang, 'promo_scope_all')
        text = t(lang, 'promo_activated_case', percent=promo['discount_percent'], scope=scope)

    await message.answer(text, reply_markup=cancel_kb("main_menu", lang), parse_mode="HTML")
