"""
KeyRush — Реферальная система и вкладка для стримеров.
"""
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from config import cfg
from database import (
    get_user, get_user_language, count_referrals,
    set_user_referred_by, add_points,
    get_streamer_by_user, get_case, set_streamer_requisites,
    create_streamer_payout, update_streamer_balance, count_streamer_customers,
)
from services.i18n import t
from services.adminlog import notify_admins, user_ref
from services.streamers import get_streamer_percents, get_streamer_min_withdraw
from keyboards import referral_kb, streamer_tab_kb, cancel_kb
from states import ReferralActivate, StreamerRequisites

router = Router()
log = logging.getLogger(__name__)

REFERRAL_CODE_PREFIX = "REF"
_bot_username_cache = None


async def _get_bot_username(bot: Bot) -> str:
    global _bot_username_cache
    if _bot_username_cache:
        return _bot_username_cache
    try:
        me = await bot.get_me()
        _bot_username_cache = me.username
    except Exception:
        log.exception("Не удалось получить username бота")
        _bot_username_cache = "KeyRushBot"
    return _bot_username_cache


def referral_code_for(user_id: int) -> str:
    return f"{REFERRAL_CODE_PREFIX}{user_id}"


def parse_referral_code(raw: str) -> int | None:
    """Достаёт user_id из реферального кода вида REF123456789 или ref123456789.
    Возвращает None, если формат неверный."""
    raw = raw.strip().upper()
    if not raw.startswith(REFERRAL_CODE_PREFIX):
        return None
    digits = raw[len(REFERRAL_CODE_PREFIX):]
    if not digits.isdigit():
        return None
    return int(digits)


async def safe_edit(callback: CallbackQuery, text: str, reply_markup=None, parse_mode="HTML"):
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


async def apply_referral(bot: Bot, new_user_id: int, referrer_id: int) -> bool:
    """Применяет реферальную привязку и начисляет баллы обеим сторонам.
    Возвращает True, если привязка реально произошла (не была установлена ранее)."""
    if referrer_id == new_user_id:
        return False
    referrer = await get_user(referrer_id)
    if not referrer:
        return False

    linked = await set_user_referred_by(new_user_id, referrer_id)
    if not linked:
        return False

    await add_points(referrer_id, cfg.REFERRAL_INVITER_POINTS)
    await add_points(new_user_id, cfg.REFERRAL_INVITED_POINTS)

    ref_lang = referrer.get('language', cfg.DEFAULT_LANG)
    try:
        await bot.send_message(
            referrer_id,
            t(ref_lang, 'referral_new_notify', points=cfg.REFERRAL_INVITER_POINTS),
            parse_mode="HTML"
        )
    except Exception:
        log.debug("Не удалось уведомить пригласившего %s", referrer_id)

    await notify_admins(
        bot,
        f"👥 <b>Новый реферал</b>\n"
        f"Пригласивший: <code>{referrer_id}</code>\n"
        f"Приглашённый: <code>{new_user_id}</code>"
    )
    return True


# ─── Меню рефералов ──────────────────────────────────────

@router.callback_query(F.data == "menu_referral")
async def menu_referral(callback: CallbackQuery, bot: Bot):
    user = await get_user(callback.from_user.id)
    lang = user.get('language', cfg.DEFAULT_LANG) if user else cfg.DEFAULT_LANG

    username = await _get_bot_username(bot)
    link = f"https://t.me/{username}?start=ref{callback.from_user.id}"
    code = referral_code_for(callback.from_user.id)
    count = await count_referrals(callback.from_user.id)

    text = t(lang, 'referral_info',
        inviter_points=cfg.REFERRAL_INVITER_POINTS,
        invited_points=cfg.REFERRAL_INVITED_POINTS,
        link=link, code=code, count=count
    )
    has_referrer = bool(user and user.get('referred_by'))
    if has_referrer:
        text += t(lang, 'referral_already_has')

    await safe_edit(callback, text, reply_markup=referral_kb(has_referrer, lang), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "referral_enter")
async def referral_enter_start(callback: CallbackQuery, state: FSMContext):
    user = await get_user(callback.from_user.id)
    lang = user.get('language', cfg.DEFAULT_LANG) if user else cfg.DEFAULT_LANG

    if user and user.get('referred_by'):
        await callback.answer(t(lang, 'referral_already_used'), show_alert=True)
        return

    await state.set_state(ReferralActivate.code)
    await safe_edit(callback,
        t(lang, 'referral_enter_prompt'),
        reply_markup=cancel_kb("menu_referral", lang),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(ReferralActivate.code)
async def referral_enter_code(message: Message, state: FSMContext, bot: Bot):
    user = await get_user(message.from_user.id)
    lang = user.get('language', cfg.DEFAULT_LANG) if user else cfg.DEFAULT_LANG
    await state.clear()

    if user and user.get('referred_by'):
        await message.answer(t(lang, 'referral_already_used'), reply_markup=cancel_kb("main_menu", lang), parse_mode="HTML")
        return

    referrer_id = parse_referral_code(message.text or "")
    if referrer_id is None:
        await message.answer(t(lang, 'referral_invalid'), reply_markup=cancel_kb("menu_referral", lang), parse_mode="HTML")
        return

    if referrer_id == message.from_user.id:
        await message.answer(t(lang, 'referral_self'), reply_markup=cancel_kb("menu_referral", lang), parse_mode="HTML")
        return

    ok = await apply_referral(bot, message.from_user.id, referrer_id)
    if not ok:
        await message.answer(t(lang, 'referral_invalid'), reply_markup=cancel_kb("menu_referral", lang), parse_mode="HTML")
        return

    await message.answer(
        t(lang, 'referral_success', points=cfg.REFERRAL_INVITED_POINTS),
        reply_markup=cancel_kb("main_menu", lang),
        parse_mode="HTML"
    )


# ─── Вкладка для стримеров ───────────────────────────────

@router.callback_query(F.data == "menu_streamers")
async def menu_streamers(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    lang = user.get('language', cfg.DEFAULT_LANG) if user else cfg.DEFAULT_LANG

    first_pct, repeat_pct = await get_streamer_percents()
    min_withdraw = await get_streamer_min_withdraw()

    streamer = await get_streamer_by_user(callback.from_user.id)

    if streamer:
        scope = "пополнение баланса"
        if streamer['promo_type'] == 'case':
            if streamer['case_id']:
                case = await get_case(streamer['case_id'])
                scope = t(lang, 'promo_scope_case', name=case['name'] if case else '?')
            else:
                scope = t(lang, 'promo_scope_all')

        customers = await count_streamer_customers(callback.from_user.id)
        text = t(lang, 'streamers_info_owner',
            code=streamer['code'],
            discount=streamer['discount_percent'],
            scope=scope,
            balance=streamer['balance_rub'],
            total_earned=streamer['total_earned_rub'],
            customers=customers,
            first_pct=first_pct,
            repeat_pct=repeat_pct,
            min_withdraw=min_withdraw,
            requisites=streamer['requisites'] or t(lang, 'streamer_requisites_none')
        )
    else:
        text = t(lang, 'streamers_info_guest',
            first_pct=first_pct, repeat_pct=repeat_pct, min_withdraw=min_withdraw,
            support_link=t(lang, 'support_link')
        )

    await safe_edit(callback, text, reply_markup=streamer_tab_kb(bool(streamer), lang), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "streamer_requisites")
async def streamer_requisites_start(callback: CallbackQuery, state: FSMContext):
    user = await get_user(callback.from_user.id)
    lang = user.get('language', cfg.DEFAULT_LANG) if user else cfg.DEFAULT_LANG

    streamer = await get_streamer_by_user(callback.from_user.id)
    if not streamer:
        await callback.answer(t(lang, 'streamer_not_a_streamer'), show_alert=True)
        return

    await state.set_state(StreamerRequisites.input)
    await safe_edit(callback,
        t(lang, 'streamer_requisites_prompt'),
        reply_markup=cancel_kb("menu_streamers", lang),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(StreamerRequisites.input)
async def streamer_requisites_save(message: Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    lang = user.get('language', cfg.DEFAULT_LANG) if user else cfg.DEFAULT_LANG
    await state.clear()

    streamer = await get_streamer_by_user(message.from_user.id)
    if not streamer:
        await message.answer(t(lang, 'streamer_not_a_streamer'), reply_markup=cancel_kb("main_menu", lang), parse_mode="HTML")
        return

    await set_streamer_requisites(message.from_user.id, message.text.strip()[:500])
    await message.answer(
        t(lang, 'streamer_requisites_saved'),
        reply_markup=cancel_kb("menu_streamers", lang),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "streamer_withdraw")
async def streamer_withdraw(callback: CallbackQuery, bot: Bot):
    user = await get_user(callback.from_user.id)
    lang = user.get('language', cfg.DEFAULT_LANG) if user else cfg.DEFAULT_LANG

    streamer = await get_streamer_by_user(callback.from_user.id)
    if not streamer:
        await callback.answer(t(lang, 'streamer_not_a_streamer'), show_alert=True)
        return

    if not streamer.get('requisites'):
        await callback.answer(t(lang, 'streamer_withdraw_no_requisites'), show_alert=True)
        return

    min_withdraw = await get_streamer_min_withdraw()
    if streamer['balance_rub'] < min_withdraw:
        await callback.answer(
            t(lang, 'streamer_withdraw_too_low', min_withdraw=min_withdraw, balance=streamer['balance_rub']),
            show_alert=True
        )
        return

    amount = streamer['balance_rub']
    # Резервируем сумму сразу, чтобы нельзя было подать вторую заявку на те же деньги.
    await update_streamer_balance(callback.from_user.id, -amount)
    payout_id = await create_streamer_payout(callback.from_user.id, amount, streamer['requisites'])

    for admin_id in cfg.ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"💸 <b>Заявка на вывод стримера</b>\n\n"
                f"👤 Стример: <code>{callback.from_user.id}</code>\n"
                f"💰 Сумма: <b>{amount}₽</b>\n"
                f"💳 Реквизиты: <code>{streamer['requisites']}</code>\n"
                f"🆔 Заявка №{payout_id}\n\n"
                f"Обработать: Админ-панель → Стримеры → Заявки на вывод.",
                parse_mode="HTML"
            )
        except Exception:
            log.exception("Не удалось уведомить админа %s о заявке на вывод", admin_id)

    await safe_edit(callback,
        t(lang, 'streamer_withdraw_success', amount=amount),
        reply_markup=cancel_kb("main_menu", lang),
        parse_mode="HTML"
    )
    await callback.answer()
