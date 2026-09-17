"""
KeyRush Admin Handlers
Полная админ-панель: кейсы, призы, ключи, экономика, рассылка
"""
import json
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import cfg
from states import (
    AdminCaseAdd, AdminPrizeAdd, AdminKeysAdd, AdminKeysDel,
    AdminCasePrizes, Broadcast, AdminPromoAdd,
    AdminStreamerAdd, AdminStreamerSettings, AdminCreditBalance,
    AdminCaseEdit, AdminPrizeEdit
)
from database import (
    create_case, get_cases, get_case, delete_case, update_case,
    create_prize, get_prizes, get_prize, update_prize,  # get_prize нужно добавить в database
    add_keys_to_prize, remove_keys_from_prize, get_case_prizes,
    set_case_prize, remove_case_prize, get_economy_stats,
    get_all_user_ids, get_user, log_broadcast,
    get_user_stats, get_case_open_stats,
    create_promocode, get_promocodes, get_promocode, get_promocode_by_code,
    set_promocode_active, delete_promocode,
    create_streamer, get_streamer_by_user, get_all_streamers, delete_streamer,
    count_streamer_customers, get_streamer_payouts, get_streamer_payout,
    set_streamer_payout_status, update_streamer_balance,
    get_setting, set_setting, delete_prize, update_user_balance
)
from services.economy import EconomySimulator
from services.adminlog import is_admin_log_enabled, set_admin_log_enabled
from services.streamers import get_streamer_percents, get_streamer_min_withdraw
from keyboards import (
    admin_panel_kb, admin_cases_kb, admin_prizes_kb, admin_keys_kb,
    admin_broadcast_kb, admin_case_actions_kb, admin_stats_kb, cancel_kb,
    admin_promo_kb, promo_type_kb, promo_case_select_kb, promo_max_uses_kb,
    promo_list_kb, promo_actions_kb,
    admin_streamers_kb, streamer_promo_type_kb, streamer_promo_case_select_kb,
    admin_streamer_list_kb, admin_streamer_view_kb, admin_streamer_payouts_kb,
    admin_streamer_payout_actions_kb, admin_streamer_settings_kb,
    admin_prize_delete_list_kb, admin_prize_delete_confirm_kb,
    admin_case_edit_menu_kb, admin_prize_list_kb, admin_prize_actions_kb,
    admin_prize_edit_menu_kb
)

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in cfg.ADMIN_IDS


async def safe_edit(callback: CallbackQuery, text: str, reply_markup=None, parse_mode="HTML"):
    """Безопасно редактирует сообщение, игнорируя 'message is not modified'."""
    # Сообщение может быть медиа (например, видео из /start) — его нельзя
    # редактировать через edit_text. Удаляем и присылаем новое текстовое.
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



# ─── Админ-вход ──────────────────────────────────────────

@router.callback_query(F.data == "admin_panel")
async def admin_panel(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    log_enabled = await is_admin_log_enabled()
    await safe_edit(callback, 
        "🔐 <b>Админ-панель KeyRush</b> 🔐",
        reply_markup=admin_panel_kb(log_enabled),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin_log_toggle")
async def admin_log_toggle(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    current = await is_admin_log_enabled()
    await set_admin_log_enabled(not current)
    new_state = not current
    log_enabled = new_state
    await safe_edit(callback,
        "🔐 <b>Админ-панель KeyRush</b> 🔐",
        reply_markup=admin_panel_kb(log_enabled),
        parse_mode="HTML"
    )
    await callback.answer(
        "🔔 Лог событий включён" if new_state else "🔕 Лог событий выключен",
        show_alert=True
    )


# ═════════════════════════════════════════════════════════
#  СТАТИСТИКА
# ═════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    ustats = await get_user_stats()
    ostats = await get_case_open_stats()

    top_cases_txt = "\n".join(
        f"   {i+1}. {c['name']} — {c['cnt']}"
        for i, c in enumerate(ostats['top_cases'])
    ) or "   —"

    top_prizes_txt = "\n".join(
        f"   {i+1}. {p['game_name']} ({p['rarity']}) — {p['cnt']}"
        for i, p in enumerate(ostats['top_prizes'])
    ) or "   —"

    top_users_txt = "\n".join(
        f"   {i+1}. {('@' + u['username']) if u['username'] else u['user_id']} — {u['cnt']} откр."
        for i, u in enumerate(ostats['top_users'])
    ) or "   —"

    text = (
        f"📈 <b>Статистика KeyRush</b>\n\n"
        f"👥 <b>Пользователи</b>\n"
        f"   Всего: <b>{ustats['total']:,}</b> | Забанено: {ustats['banned']}\n"
        f"   Новых сегодня: <b>{ustats['new_today']}</b> | за 7 дн: {ustats['new_week']} | за 30 дн: {ustats['new_month']}\n"
        f"   Открывали хоть раз: {ustats['active_openers']}\n"
        f"   Активны сегодня: {ustats['active_today']} | за 7 дн: {ustats['active_week']}\n"
        f"   Суммарный баланс всех юзеров: {ustats['total_balance']:,}₽\n\n"
        f"🎲 <b>Открытия кейсов</b>\n"
        f"   Всего открытий: <b>{ostats['total_opens']:,}</b>\n"
        f"   Сегодня: <b>{ostats['opens_today']}</b> | за 7 дн: {ostats['opens_week']}\n"
        f"   Выручка сегодня: {ostats['revenue_today']:,}₽\n\n"
        f"🏆 <b>Топ кейсов по открытиям</b>\n{top_cases_txt}\n\n"
        f"💎 <b>Топ призов по выпадениям</b>\n{top_prizes_txt}\n\n"
        f"🥇 <b>Топ игроков по открытиям</b>\n{top_users_txt}"
    )

    await safe_edit(callback, text, reply_markup=admin_stats_kb(), parse_mode="HTML")
    await callback.answer()


# ═════════════════════════════════════════════════════════
#  УПРАВЛЕНИЕ КЕЙСАМИ
# ═════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin_cases")
async def admin_cases(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    await safe_edit(callback, 
        "📦 <b>Управление кейсами</b>",
        reply_markup=admin_cases_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


# ─── Добавить кейс ───────────────────────────────────────

@router.callback_query(F.data == "admin_case_add")
async def admin_case_add_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminCaseAdd.name)
    await safe_edit(callback, 
        "➕ <b>Новый кейс</b>\n\n"
        "Введи название кейса:",
        reply_markup=cancel_kb("admin_cases"),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminCaseAdd.name)
async def admin_case_add_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AdminCaseAdd.description)
    await message.answer(
        "📝 Введи описание кейса:",
        reply_markup=cancel_kb("admin_cases")
    )


@router.message(AdminCaseAdd.description)
async def admin_case_add_desc(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await state.set_state(AdminCaseAdd.price)
    await message.answer(
        "💰 Введи цену открытия (в рублях, числом):",
        reply_markup=cancel_kb("admin_cases")
    )


@router.message(AdminCaseAdd.price)
async def admin_case_add_price(message: Message, state: FSMContext):
    try:
        price = int(message.text)
    except ValueError:
        await message.answer("❌ Введи число!")
        return

    await state.update_data(price=price)
    await state.set_state(AdminCaseAdd.image)
    await message.answer(
        "🖼 Отправь изображение кейса (или напиши 'пропустить'):",
        reply_markup=cancel_kb("admin_cases")
    )


@router.message(AdminCaseAdd.image)
async def admin_case_add_image(message: Message, state: FSMContext):
    data = await state.get_data()
    image_url = None

    if message.photo:
        image_url = message.photo[-1].file_id
    elif message.text and message.text.lower() != "пропустить":
        image_url = message.text

    case_id = await create_case(
        data['name'],
        data['description'],
        data['price'],
        image_url
    )

    await state.clear()
    await message.answer(
        f"✅ Кейс <b>{data['name']}</b> создан!\n"
        f"ID: <code>{case_id}</code>",
        reply_markup=admin_cases_kb(),
        parse_mode="HTML"
    )


# ─── Список кейсов ───────────────────────────────────────

@router.callback_query(F.data == "admin_case_list")
async def admin_case_list(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    cases = await get_cases(active_only=False)
    if not cases:
        await safe_edit(callback, 
            "😕 Кейсов пока нет.",
            reply_markup=admin_cases_kb(),
            parse_mode="HTML"
        )
        await callback.answer()
        return

    text = "📦 <b>Список кейсов:</b>\n\n"
    for c in cases:
        status = "🟢" if c['is_active'] else "🔴"
        text += f"{status} <b>{c['name']}</b> — {c['price']}₽ (ID: {c['case_id']})\n"

    # Кнопки для каждого кейса
    builder = InlineKeyboardBuilder()
    for c in cases:
        builder.row(InlineKeyboardButton(
            text=f"⚙️ {c['name']}",
            callback_data=f"admin_case_edit:{c['case_id']}"
        ))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_cases"))

    await safe_edit(callback, text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("admin_case_edit:"))
async def admin_case_edit(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    case_id = int(callback.data.split(":")[1])
    case = await get_case(case_id)
    if not case:
        await callback.answer("Кейс не найден", show_alert=True)
        return

    text = (
        f"⚙️ <b>{case['name']}</b>\n"
        f"💰 Цена: {case['price']}₽\n"
        f"📝 {case['description'] or '—'}\n"
        f"🖼 Изображение: {'есть' if case.get('image_url') else 'нет'}\n"
        f"🆔 ID: {case['case_id']}"
    )
    await safe_edit(callback, 
        text,
        reply_markup=admin_case_actions_kb(case_id),
        parse_mode="HTML"
    )
    await callback.answer()


# ─── Редактировать кейс ──────────────────────────────────

@router.callback_query(F.data.startswith("admin_case_edit_menu:"))
async def admin_case_edit_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    case_id = int(callback.data.split(":")[1])
    case = await get_case(case_id)
    if not case:
        await callback.answer("Кейс не найден", show_alert=True)
        return

    await safe_edit(callback,
        f"✏️ <b>Редактирование кейса «{case['name']}»</b>\n\n"
        f"Выбери, что изменить:",
        reply_markup=admin_case_edit_menu_kb(case_id),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("acedit_name:"))
async def acedit_name_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    case_id = int(callback.data.split(":")[1])
    await state.update_data(case_id=case_id)
    await state.set_state(AdminCaseEdit.name)
    await safe_edit(callback,
        "✏️ Введи новое название кейса:",
        reply_markup=cancel_kb(f"admin_case_edit_menu:{case_id}"),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminCaseEdit.name)
async def acedit_name_save(message: Message, state: FSMContext):
    data = await state.get_data()
    case_id = data['case_id']
    await update_case(case_id, name=message.text)
    await state.clear()
    await message.answer(
        "✅ Название кейса обновлено.",
        reply_markup=admin_case_edit_menu_kb(case_id),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("acedit_desc:"))
async def acedit_desc_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    case_id = int(callback.data.split(":")[1])
    await state.update_data(case_id=case_id)
    await state.set_state(AdminCaseEdit.description)
    await safe_edit(callback,
        "📝 Введи новое описание кейса:",
        reply_markup=cancel_kb(f"admin_case_edit_menu:{case_id}"),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminCaseEdit.description)
async def acedit_desc_save(message: Message, state: FSMContext):
    data = await state.get_data()
    case_id = data['case_id']
    await update_case(case_id, description=message.text)
    await state.clear()
    await message.answer(
        "✅ Описание кейса обновлено.",
        reply_markup=admin_case_edit_menu_kb(case_id),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("acedit_price:"))
async def acedit_price_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    case_id = int(callback.data.split(":")[1])
    await state.update_data(case_id=case_id)
    await state.set_state(AdminCaseEdit.price)
    await safe_edit(callback,
        "💰 Введи новую цену открытия (в рублях, числом):",
        reply_markup=cancel_kb(f"admin_case_edit_menu:{case_id}"),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminCaseEdit.price)
async def acedit_price_save(message: Message, state: FSMContext):
    try:
        price = int(message.text)
    except ValueError:
        await message.answer("❌ Введи число!")
        return
    data = await state.get_data()
    case_id = data['case_id']
    await update_case(case_id, price=price)
    await state.clear()
    await message.answer(
        "✅ Цена кейса обновлена.",
        reply_markup=admin_case_edit_menu_kb(case_id),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("acedit_image_del:"))
async def acedit_image_del(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    case_id = int(callback.data.split(":")[1])
    await update_case(case_id, image_url=None)
    await callback.answer("Изображение убрано", show_alert=True)
    await admin_case_edit_menu(callback)


@router.callback_query(F.data.startswith("acedit_image:"))
async def acedit_image_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    case_id = int(callback.data.split(":")[1])
    await state.update_data(case_id=case_id)
    await state.set_state(AdminCaseEdit.image)
    await safe_edit(callback,
        "🖼 Отправь новое изображение кейса:",
        reply_markup=cancel_kb(f"admin_case_edit_menu:{case_id}"),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminCaseEdit.image)
async def acedit_image_save(message: Message, state: FSMContext):
    if not message.photo and not message.text:
        await message.answer("❌ Отправь фото или ссылку на изображение!")
        return
    image_url = message.photo[-1].file_id if message.photo else message.text
    data = await state.get_data()
    case_id = data['case_id']
    await update_case(case_id, image_url=image_url)
    await state.clear()
    await message.answer(
        "✅ Изображение кейса обновлено.",
        reply_markup=admin_case_edit_menu_kb(case_id),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("admin_case_del:"))
async def admin_case_del(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    case_id = int(callback.data.split(":")[1])
    await delete_case(case_id)
    await safe_edit(callback, 
        "🗑 Кейс удалён.",
        reply_markup=admin_cases_kb(),
        parse_mode="HTML"
    )
    await callback.answer("Удалено")


# ─── Настроить призы в кейсе ─────────────────────────────

@router.callback_query(F.data.startswith("admin_case_prizes:"))
async def admin_case_prizes_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    case_id = int(callback.data.split(":")[1])
    await state.update_data(case_id=case_id)
    await state.set_state(AdminCasePrizes.select_prize)

    prizes = await get_prizes()
    current = await get_case_prizes(case_id)
    current_ids = {p['prize_id'] for p in current}

    text = "🎁 <b>Выбери приз для добавления в кейс:</b>\n\n"
    text += "<b>Текущие призы:</b>\n"
    for p in current:
        text += f"  • {p['game_name']} (вес: {p['weight']})\n"

    builder = InlineKeyboardBuilder()
    for p in prizes:
        if p['prize_id'] not in current_ids:
            builder.row(InlineKeyboardButton(
                text=f"➕ {p['game_name']}",
                callback_data=f"acp_prize:{p['prize_id']}"
            ))

    for p in current:
        builder.row(InlineKeyboardButton(
            text=f"🗑 Убрать {p['game_name']}",
            callback_data=f"acp_remove:{case_id}:{p['prize_id']}"
        ))

    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data=f"admin_case_edit:{case_id}"))

    await safe_edit(callback, text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("acp_prize:"))
async def admin_case_prize_select(callback: CallbackQuery, state: FSMContext):
    prize_id = int(callback.data.split(":")[1])
    await state.update_data(prize_id=prize_id)
    await state.set_state(AdminCasePrizes.set_weight)

    await safe_edit(callback, 
        "⚖️ Введи <b>вес</b> (вероятность) для этого приза в кейсе.\n"
        "Чем больше число — тем выше шанс выпадения.\n"
        "Например: 50 (обычный), 10 (редкий), 1 (легендарный)",
        reply_markup=cancel_kb("admin_cases"),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminCasePrizes.set_weight)
async def admin_case_prize_weight(message: Message, state: FSMContext):
    try:
        weight = float(message.text)
    except ValueError:
        await message.answer("❌ Введи число!")
        return

    data = await state.get_data()
    await set_case_prize(data['case_id'], data['prize_id'], weight)
    await state.clear()

    await message.answer(
        f"✅ Приз добавлен в кейс с весом {weight}!",
        reply_markup=cancel_kb(f"admin_case_edit:{data['case_id']}"),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("acp_remove:"))
async def admin_case_prize_remove(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    case_id = int(parts[1])
    prize_id = int(parts[2])
    await state.update_data(case_id=case_id)
    await remove_case_prize(case_id, prize_id)
    await callback.answer("Приз убран из кейса")
    # Перезагружаем список
    await admin_case_prizes_start(callback, state)


# ═════════════════════════════════════════════════════════
#  УПРАВЛЕНИЕ ПРИЗАМИ
# ═════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin_prizes")
async def admin_prizes(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    await safe_edit(callback, 
        "🎁 <b>Управление призами</b>",
        reply_markup=admin_prizes_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin_prize_add")
async def admin_prize_add_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminPrizeAdd.game_name)
    await safe_edit(callback, 
        "➕ <b>Новый приз</b>\n\n"
        "Введи название игры:",
        reply_markup=cancel_kb("admin_prizes"),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminPrizeAdd.game_name)
async def admin_prize_add_name(message: Message, state: FSMContext):
    await state.update_data(game_name=message.text)
    await state.set_state(AdminPrizeAdd.rarity)

    builder = InlineKeyboardBuilder()
    for r in ['common', 'uncommon', 'rare', 'epic', 'legendary']:
        builder.row(InlineKeyboardButton(text=r, callback_data=f"prize_rarity:{r}"))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="admin_prizes"))

    await message.answer(
        "🎨 Выбери редкость приза:",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data.startswith("prize_rarity:"))
async def admin_prize_rarity(callback: CallbackQuery, state: FSMContext):
    rarity = callback.data.split(":")[1]
    await state.update_data(rarity=rarity)
    await state.set_state(AdminPrizeAdd.market_value)
    await safe_edit(callback, 
        "💰 Введи <b>рыночную стоимость</b> игры (в рублях):",
        reply_markup=cancel_kb("admin_prizes"),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminPrizeAdd.market_value)
async def admin_prize_add_market(message: Message, state: FSMContext):
    try:
        val = int(message.text)
    except ValueError:
        await message.answer("❌ Введи число!")
        return
    await state.update_data(market_value=val)
    await state.set_state(AdminPrizeAdd.cost_price)
    await message.answer(
        "🏷 Введи <b>себестоимость</b> (сколько ты платишь поставщику):",
        reply_markup=cancel_kb("admin_prizes")
    )


@router.message(AdminPrizeAdd.cost_price)
async def admin_prize_add_cost(message: Message, state: FSMContext):
    try:
        val = int(message.text)
    except ValueError:
        await message.answer("❌ Введи число!")
        return

    await state.update_data(cost_price=val)
    await state.set_state(AdminPrizeAdd.description)
    await message.answer(
        "📝 Введи описание приза (или напиши 'пропустить'):",
        reply_markup=cancel_kb("admin_prizes")
    )


@router.message(AdminPrizeAdd.description)
async def admin_prize_add_desc(message: Message, state: FSMContext):
    description = None if message.text.strip().lower() == "пропустить" else message.text
    await state.update_data(description=description)
    await state.set_state(AdminPrizeAdd.image)
    await message.answer(
        "🖼 Отправь изображение приза (или напиши 'пропустить'):",
        reply_markup=cancel_kb("admin_prizes")
    )


@router.message(AdminPrizeAdd.image)
async def admin_prize_add_image(message: Message, state: FSMContext):
    data = await state.get_data()
    image_url = None
    if message.photo:
        image_url = message.photo[-1].file_id
    elif message.text and message.text.lower() != "пропустить":
        image_url = message.text

    prize_id = await create_prize(
        data['game_name'],
        data['rarity'],
        data['market_value'],
        data['cost_price'],
        description=data.get('description'),
        image_url=image_url
    )
    await state.clear()

    await message.answer(
        f"✅ Приз <b>{data['game_name']}</b> создан!\n"
        f"ID: <code>{prize_id}</code>",
        reply_markup=admin_prizes_kb(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "admin_prize_list")
async def admin_prize_list(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    prizes = await get_prizes()
    if not prizes:
        await safe_edit(callback, 
            "😕 Призов пока нет.",
            reply_markup=admin_prizes_kb(),
            parse_mode="HTML"
        )
        await callback.answer()
        return

    await safe_edit(callback,
        "🎁 <b>Список призов:</b>\n\nВыбери приз для просмотра/редактирования:",
        reply_markup=admin_prize_list_kb(prizes),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_prize_edit:"))
async def admin_prize_edit(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    prize_id = int(callback.data.split(":")[1])
    prize = await get_prize(prize_id)
    if not prize:
        await callback.answer("Приз не найден", show_alert=True)
        return

    text = (
        f"🎮 <b>{prize['game_name']}</b>\n"
        f"🎨 Редкость: {prize['rarity']}\n"
        f"💰 Рынок: {prize['market_value']}₽ | 🏷 Себестоимость: {prize['cost_price']}₽\n"
        f"🔑 Ключей: {prize['available_keys']}/{prize['total_keys']}\n"
        f"📝 {prize.get('description') or '—'}\n"
        f"🖼 Изображение: {'есть' if prize.get('image_url') else 'нет'}\n"
        f"🆔 ID: {prize['prize_id']}"
    )
    await safe_edit(callback, text, reply_markup=admin_prize_actions_kb(prize_id), parse_mode="HTML")
    await callback.answer()


# ─── Редактировать приз ──────────────────────────────────

@router.callback_query(F.data.startswith("admin_prize_edit_menu:"))
async def admin_prize_edit_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    prize_id = int(callback.data.split(":")[1])
    prize = await get_prize(prize_id)
    if not prize:
        await callback.answer("Приз не найден", show_alert=True)
        return

    await safe_edit(callback,
        f"✏️ <b>Редактирование приза «{prize['game_name']}»</b>\n\n"
        f"Выбери, что изменить:",
        reply_markup=admin_prize_edit_menu_kb(prize_id),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("apedit_name:"))
async def apedit_name_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    prize_id = int(callback.data.split(":")[1])
    await state.update_data(prize_id=prize_id)
    await state.set_state(AdminPrizeEdit.game_name)
    await safe_edit(callback,
        "✏️ Введи новое название игры:",
        reply_markup=cancel_kb(f"admin_prize_edit_menu:{prize_id}"),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminPrizeEdit.game_name)
async def apedit_name_save(message: Message, state: FSMContext):
    data = await state.get_data()
    prize_id = data['prize_id']
    await update_prize(prize_id, game_name=message.text)
    await state.clear()
    await message.answer(
        "✅ Название приза обновлено.",
        reply_markup=admin_prize_edit_menu_kb(prize_id),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("apedit_desc:"))
async def apedit_desc_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    prize_id = int(callback.data.split(":")[1])
    await state.update_data(prize_id=prize_id)
    await state.set_state(AdminPrizeEdit.description)
    await safe_edit(callback,
        "📝 Введи новое описание приза:",
        reply_markup=cancel_kb(f"admin_prize_edit_menu:{prize_id}"),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminPrizeEdit.description)
async def apedit_desc_save(message: Message, state: FSMContext):
    data = await state.get_data()
    prize_id = data['prize_id']
    await update_prize(prize_id, description=message.text)
    await state.clear()
    await message.answer(
        "✅ Описание приза обновлено.",
        reply_markup=admin_prize_edit_menu_kb(prize_id),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("apedit_image_del:"))
async def apedit_image_del(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    prize_id = int(callback.data.split(":")[1])
    await update_prize(prize_id, image_url=None)
    await callback.answer("Изображение убрано", show_alert=True)
    await admin_prize_edit_menu(callback)


@router.callback_query(F.data.startswith("apedit_image:"))
async def apedit_image_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    prize_id = int(callback.data.split(":")[1])
    await state.update_data(prize_id=prize_id)
    await state.set_state(AdminPrizeEdit.image)
    await safe_edit(callback,
        "🖼 Отправь новое изображение приза:",
        reply_markup=cancel_kb(f"admin_prize_edit_menu:{prize_id}"),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminPrizeEdit.image)
async def apedit_image_save(message: Message, state: FSMContext):
    if not message.photo and not message.text:
        await message.answer("❌ Отправь фото или ссылку на изображение!")
        return
    image_url = message.photo[-1].file_id if message.photo else message.text
    data = await state.get_data()
    prize_id = data['prize_id']
    await update_prize(prize_id, image_url=image_url)
    await state.clear()
    await message.answer(
        "✅ Изображение приза обновлено.",
        reply_markup=admin_prize_edit_menu_kb(prize_id),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "admin_prize_del_list")
async def admin_prize_del_list(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    prizes = await get_prizes()
    if not prizes:
        await safe_edit(callback,
            "😕 Призов пока нет.",
            reply_markup=admin_prizes_kb(),
            parse_mode="HTML"
        )
        await callback.answer()
        return

    await safe_edit(callback,
        "🗑 <b>Выбери приз для удаления:</b>\n\n"
        "⚠️ Удаление приза уберёт его из всех кейсов и удалит его нераспределённые ключи. "
        "Ключи, уже выданные пользователям в инвентарь, останутся у них.",
        reply_markup=admin_prize_delete_list_kb(prizes),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_prize_del:"))
async def admin_prize_del_confirm(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    prize_id = int(callback.data.split(":")[1])
    prize = await get_prize(prize_id)
    if not prize:
        await callback.answer("Приз не найден", show_alert=True)
        return

    await safe_edit(callback,
        f"⚠️ <b>Удалить приз «{prize['game_name']}»?</b>\n\n"
        f"Редкость: {prize['rarity']}\n"
        f"Ключей в наличии: {prize['available_keys']}/{prize['total_keys']}\n\n"
        f"Это действие нельзя отменить.",
        reply_markup=admin_prize_delete_confirm_kb(prize_id),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_prize_del_confirm:"))
async def admin_prize_del_execute(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    prize_id = int(callback.data.split(":")[1])
    prize = await get_prize(prize_id)
    if not prize:
        await callback.answer("Приз уже удалён", show_alert=True)
        return

    await delete_prize(prize_id)

    await safe_edit(callback,
        f"🗑 Приз «{prize['game_name']}» удалён.",
        reply_markup=admin_prizes_kb(),
        parse_mode="HTML"
    )
    await callback.answer("Удалено")


# ═════════════════════════════════════════════════════════
#  УПРАВЛЕНИЕ КЛЮЧАМИ
# ═════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin_keys")
async def admin_keys(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    await safe_edit(callback, 
        "🔑 <b>Управление ключами</b>",
        reply_markup=admin_keys_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin_keys_add")
async def admin_keys_add_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    prizes = await get_prizes()
    if not prizes:
        await callback.answer("Сначала создай призы!", show_alert=True)
        return

    await state.set_state(AdminKeysAdd.select_prize)
    builder = InlineKeyboardBuilder()
    for p in prizes:
        builder.row(InlineKeyboardButton(
            text=f"{p['game_name']} (доступно: {p['available_keys']})",
            callback_data=f"keysadd_prize:{p['prize_id']}"
        ))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="admin_keys"))

    await safe_edit(callback, 
        "➕ <b>Добавление ключей</b>\n\n"
        "Выбери приз:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("keysadd_prize:"))
async def admin_keys_add_prize(callback: CallbackQuery, state: FSMContext):
    prize_id = int(callback.data.split(":")[1])
    await state.update_data(prize_id=prize_id)
    await state.set_state(AdminKeysAdd.input_keys)
    await safe_edit(callback, 
        "📝 Отправь ключи <b>по одному на строку</b>.\n"
        "Можно отправить сразу много строк:",
        reply_markup=cancel_kb("admin_keys"),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminKeysAdd.input_keys)
async def admin_keys_add_input(message: Message, state: FSMContext):
    keys = [k.strip() for k in message.text.split("\n") if k.strip()]
    if not keys:
        await message.answer("❌ Ключи не найдены. Отправь по одному на строку.")
        return

    await state.update_data(keys=keys)
    await state.set_state(AdminKeysAdd.confirm)

    data = await state.get_data()
    await message.answer(
        f"📦 Будет добавлено <b>{len(keys)}</b> ключей.\n"
        f"Подтверждаешь?",
        reply_markup=InlineKeyboardBuilder().row(
            InlineKeyboardButton(text="✅ Да", callback_data="keysadd_confirm"),
            InlineKeyboardButton(text="❌ Нет", callback_data="admin_keys")
        ).as_markup(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "keysadd_confirm")
async def admin_keys_add_confirm(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await add_keys_to_prize(data['prize_id'], data['keys'])
    await state.clear()
    await safe_edit(callback, 
        f"✅ Добавлено <b>{len(data['keys'])}</b> ключей!",
        reply_markup=admin_keys_kb(),
        parse_mode="HTML"
    )
    await callback.answer("Готово!")


@router.callback_query(F.data == "admin_keys_del")
async def admin_keys_del_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    prizes = await get_prizes()
    if not prizes:
        await callback.answer("Нет призов", show_alert=True)
        return

    await state.set_state(AdminKeysDel.select_prize)
    builder = InlineKeyboardBuilder()
    for p in prizes:
        if p['available_keys'] > 0:
            builder.row(InlineKeyboardButton(
                text=f"{p['game_name']} (доступно: {p['available_keys']})",
                callback_data=f"keysdel_prize:{p['prize_id']}"
            ))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="admin_keys"))

    await safe_edit(callback, 
        "🗑 <b>Удаление ключей</b>\n\n"
        "Выбери приз:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("keysdel_prize:"))
async def admin_keys_del_prize(callback: CallbackQuery, state: FSMContext):
    prize_id = int(callback.data.split(":")[1])
    await state.update_data(prize_id=prize_id)
    await state.set_state(AdminKeysDel.input_count)
    await safe_edit(callback, 
        "🔢 Введи количество ключей для удаления:",
        reply_markup=cancel_kb("admin_keys"),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminKeysDel.input_count)
async def admin_keys_del_count(message: Message, state: FSMContext):
    try:
        count = int(message.text)
    except ValueError:
        await message.answer("❌ Введи число!")
        return

    data = await state.get_data()
    removed = await remove_keys_from_prize(data['prize_id'], count)
    await state.clear()

    await message.answer(
        f"🗑 Удалено <b>{removed}</b> ключей.",
        reply_markup=admin_keys_kb(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "admin_keys_inv")
async def admin_keys_inv(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    prizes = await get_prizes()
    text = "📦 <b>Инвентарь ключей:</b>\n\n"
    for p in prizes:
        text += f"🎮 {p['game_name']}: <b>{p['available_keys']}</b> / {p['total_keys']}\n"

    await safe_edit(callback, text, reply_markup=admin_keys_kb(), parse_mode="HTML")
    await callback.answer()


# ═════════════════════════════════════════════════════════
#  ЭКОНОМИКА
# ═════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin_economy")
async def admin_economy(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    stats = await get_economy_stats()
    funds = stats['funds']

    text = (
        f"📊 <b>Экономика KeyRush</b>\n\n"
        f"💰 <b>Оборот:</b> {stats['revenue']:,}₽\n"
        f"🎲 <b>Открытий:</b> {stats['total_opens']:,}\n"
        f"📦 <b>Себестоимость призов:</b> {stats['total_cost']:,}₽\n"
        f"📈 <b>Средняя стоимость приза:</b> {stats['avg_prize_cost']}₽\n"
        f"🎯 <b>RTP:</b> {stats['rtp']}%\n"
        f"📉 <b>Маржа:</b> {stats['margin']}%\n\n"
        f"💎 <b>Prize Fund:</b> {funds.get('prize_fund', 0):,}₽\n"
        f"🛡 <b>Reserve:</b> {funds.get('reserve', 0):,}₽\n"
        f"⚙️ <b>Operating:</b> {funds.get('operating', 0):,}₽\n"
        f"💵 <b>Profit:</b> {funds.get('profit', 0):,}₽\n"
        f"🏦 <b>Available:</b> {funds.get('available', 0):,}₽"
    )

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🧪 Симуляция", callback_data="admin_simulate"))
    builder.row(InlineKeyboardButton(text="🔙 Админ-панель", callback_data="admin_panel"))

    await safe_edit(callback, text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin_simulate")
async def admin_simulate(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    # Берём первый активный кейс для симуляции
    cases = await get_cases(active_only=True)
    if not cases:
        await callback.answer("Нет активных кейсов", show_alert=True)
        return

    case = cases[0]
    prizes = await get_case_prizes(case['case_id'])
    if not prizes:
        await callback.answer("В кейсе нет призов", show_alert=True)
        return

    text = f"🧪 <b>Симуляция для кейса '{case['name']}'</b>\n\n"

    for n in [100, 1000, 10000]:
        sim = EconomySimulator.simulate(prizes, case['price'], n)
        text += (
            f"📊 <b>{n:,} открытий:</b>\n"
            f"   Оборот: {sim['revenue']:,}₽\n"
            f"   Себестоимость: {sim['total_prize_cost']:,}₽\n"
            f"   RTP: {sim['rtp']}% | Маржа: {sim['margin']}%\n"
            f"   Prize Fund: {sim['prize_fund_accumulated']:,}₽\n"
            f"   Дорогих призов можно купить: ~{sim['expensive_prizes_affordable']}\n\n"
        )

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_economy"))

    # Разбиваем на части если слишком длинно
    if len(text) > 4000:
        text = text[:3900] + "\n\n...(обрезано)"

    await safe_edit(callback, text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


# ═════════════════════════════════════════════════════════
#  ПРОМОКОДЫ
# ═════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin_promo")
async def admin_promo(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.clear()
    await safe_edit(callback,
        "🎟 <b>Управление промокодами</b>\n\n"
        "Промокоды бывают двух типов:\n"
        "• 💰 <b>Скидка на пополнение</b> — добавляет процент к баллам,\n"
        "  начисляемым при следующем пополнении баланса.\n"
        "• 🎲 <b>Скидка на открытие кейса</b> — снижает цену открытия\n"
        "  конкретного кейса или всех кейсов на процент.",
        reply_markup=admin_promo_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


# ─── Добавить промокод ───────────────────────────────────

@router.callback_query(F.data == "admin_promo_add")
async def admin_promo_add_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminPromoAdd.code)
    await safe_edit(callback,
        "➕ <b>Новый промокод</b>\n\n"
        "Введи код промокода (например, <code>SALE25</code>):",
        reply_markup=cancel_kb("admin_promo"),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminPromoAdd.code)
async def admin_promo_add_code(message: Message, state: FSMContext):
    code = message.text.strip().upper()
    if not code or " " in code:
        await message.answer("❌ Код не должен содержать пробелов. Попробуй ещё раз:")
        return

    existing = await get_promocode_by_code(code)
    if existing:
        await message.answer(
            f"❌ Промокод <code>{code}</code> уже существует. Введи другой код:",
            parse_mode="HTML"
        )
        return

    await state.update_data(code=code)
    await state.set_state(AdminPromoAdd.promo_type)
    await message.answer(
        "🏷 Выбери тип промокода:",
        reply_markup=promo_type_kb()
    )


@router.callback_query(F.data.startswith("promo_type:"))
async def admin_promo_type(callback: CallbackQuery, state: FSMContext):
    promo_type = callback.data.split(":")[1]
    await state.update_data(promo_type=promo_type, case_id=None)

    if promo_type == "case":
        cases = await get_cases(active_only=False)
        await state.set_state(AdminPromoAdd.case_select)
        await safe_edit(callback,
            "🎲 На какой кейс распространяется скидка?",
            reply_markup=promo_case_select_kb(cases),
            parse_mode="HTML"
        )
    else:
        await state.set_state(AdminPromoAdd.discount)
        await safe_edit(callback,
            "💯 Введи размер скидки в процентах (например, <code>25</code> — это +25% к баллам сверх обычных 25%):",
            reply_markup=cancel_kb("admin_promo"),
            parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data.startswith("promo_case:"))
async def admin_promo_case_select(callback: CallbackQuery, state: FSMContext):
    value = callback.data.split(":", 1)[1]
    case_id = None if value == "all" else int(value)
    await state.update_data(case_id=case_id)
    await state.set_state(AdminPromoAdd.discount)
    await safe_edit(callback,
        "💯 Введи размер скидки в процентах (например, <code>15</code> — это -15% к цене открытия):",
        reply_markup=cancel_kb("admin_promo"),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminPromoAdd.discount)
async def admin_promo_add_discount(message: Message, state: FSMContext):
    try:
        discount = float(message.text.replace(",", ".").replace("%", "").strip())
    except ValueError:
        await message.answer("❌ Введи число, например 25")
        return

    if discount <= 0 or discount > 100:
        await message.answer("❌ Скидка должна быть от 1 до 100")
        return

    await state.update_data(discount=discount)
    await state.set_state(AdminPromoAdd.max_uses)
    await message.answer(
        "🔢 Введи максимальное количество использований промокода (числом),\n"
        "или нажми «Без ограничения»:",
        reply_markup=promo_max_uses_kb()
    )


@router.callback_query(F.data == "promo_unlimited")
async def admin_promo_unlimited(callback: CallbackQuery, state: FSMContext):
    await state.update_data(max_uses=None)
    await _show_promo_confirm(callback.message, state)
    await callback.answer()


@router.message(AdminPromoAdd.max_uses)
async def admin_promo_add_max_uses(message: Message, state: FSMContext):
    try:
        max_uses = int(message.text.strip())
        if max_uses <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи целое положительное число или нажми «Без ограничения»")
        return

    await state.update_data(max_uses=max_uses)
    await _show_promo_confirm(message, state)


async def _show_promo_confirm(target, state: FSMContext):
    data = await state.get_data()
    await state.set_state(AdminPromoAdd.confirm)

    type_label = "💰 Скидка на пополнение" if data['promo_type'] == 'deposit' else "🎲 Скидка на открытие кейса"

    scope_label = ""
    if data['promo_type'] == 'case':
        if data.get('case_id'):
            case = await get_case(data['case_id'])
            scope_label = f"\n🎯 Кейс: <b>{case['name'] if case else '?'}</b>"
        else:
            scope_label = "\n🎯 Кейс: <b>все кейсы</b>"

    max_uses_label = data['max_uses'] if data.get('max_uses') else "без ограничения"

    text = (
        f"🎟 <b>Проверь промокод перед созданием:</b>\n\n"
        f"🔑 Код: <code>{data['code']}</code>\n"
        f"🏷 Тип: {type_label}{scope_label}\n"
        f"💯 Скидка: <b>{data['discount']}%</b>\n"
        f"🔢 Лимит использований: <b>{max_uses_label}</b>\n\n"
        f"Создать промокод?"
    )

    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="✅ Создать", callback_data="promo_confirm_create"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="admin_promo")
    )

    if hasattr(target, 'edit_text'):
        try:
            await target.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")
        except TelegramBadRequest:
            await target.answer(text, reply_markup=kb.as_markup(), parse_mode="HTML")
    else:
        await target.answer(text, reply_markup=kb.as_markup(), parse_mode="HTML")


@router.callback_query(F.data == "promo_confirm_create")
async def admin_promo_confirm_create(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    promo_id = await create_promocode(
        code=data['code'],
        promo_type=data['promo_type'],
        discount_percent=data['discount'],
        case_id=data.get('case_id'),
        max_uses=data.get('max_uses')
    )
    await state.clear()

    await safe_edit(callback,
        f"✅ Промокод <code>{data['code']}</code> создан!\n"
        f"ID: <code>{promo_id}</code>",
        reply_markup=admin_promo_kb(),
        parse_mode="HTML"
    )
    await callback.answer("Промокод создан!")


# ─── Список промокодов ───────────────────────────────────

@router.callback_query(F.data == "admin_promo_list")
async def admin_promo_list(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    promos = await get_promocodes()
    if not promos:
        await safe_edit(callback,
            "😕 Промокодов пока нет.",
            reply_markup=admin_promo_kb(),
            parse_mode="HTML"
        )
        await callback.answer()
        return

    await safe_edit(callback,
        "🎟 <b>Список промокодов:</b>\n\n🟢 — активен, 🔴 — выключен",
        reply_markup=promo_list_kb(promos),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_promo_view:"))
async def admin_promo_view(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    promo_id = int(callback.data.split(":")[1])
    promo = await get_promocode(promo_id)
    if not promo:
        await callback.answer("Промокод не найден", show_alert=True)
        return

    type_label = "💰 Скидка на пополнение" if promo['promo_type'] == 'deposit' else "🎲 Скидка на открытие кейса"
    scope_label = ""
    if promo['promo_type'] == 'case':
        if promo['case_id']:
            case = await get_case(promo['case_id'])
            scope_label = f"\n🎯 Кейс: <b>{case['name'] if case else '?'}</b>"
        else:
            scope_label = "\n🎯 Кейс: <b>все кейсы</b>"

    max_uses_label = promo['max_uses'] if promo['max_uses'] else "без ограничения"
    status_label = "🟢 Активен" if promo['is_active'] else "🔴 Выключен"

    text = (
        f"🎟 <b>{promo['code']}</b>\n\n"
        f"🏷 Тип: {type_label}{scope_label}\n"
        f"💯 Скидка: <b>{promo['discount_percent']}%</b>\n"
        f"🔢 Использовано: <b>{promo['used_count']}</b> / {max_uses_label}\n"
        f"📊 Статус: {status_label}"
    )

    await safe_edit(callback, text, reply_markup=promo_actions_kb(promo_id, bool(promo['is_active'])), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("admin_promo_toggle:"))
async def admin_promo_toggle(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    promo_id = int(callback.data.split(":")[1])
    promo = await get_promocode(promo_id)
    if not promo:
        await callback.answer("Промокод не найден", show_alert=True)
        return
    await set_promocode_active(promo_id, not promo['is_active'])
    await callback.answer("Статус изменён")
    await admin_promo_view(callback)


@router.callback_query(F.data.startswith("admin_promo_del:"))
async def admin_promo_del(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    promo_id = int(callback.data.split(":")[1])
    await delete_promocode(promo_id)
    await safe_edit(callback,
        "🗑 Промокод удалён.",
        reply_markup=admin_promo_kb(),
        parse_mode="HTML"
    )
    await callback.answer("Удалено")


# ═════════════════════════════════════════════════════════
#  РАССЫЛКА
# ═════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(Broadcast.target_type)
    await safe_edit(callback, 
        "📢 <b>Рассылка сообщений</b>\n\n"
        "Выбери тип рассылки:",
        reply_markup=admin_broadcast_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("broadcast:"))
async def broadcast_target(callback: CallbackQuery, state: FSMContext):
    target = callback.data.split(":")[1]
    await state.update_data(target_type=target)

    if target == "all":
        await state.update_data(target_value="all")
        await state.set_state(Broadcast.input_text)
        await safe_edit(callback, 
            "📝 Введи текст сообщения (поддерживается HTML):",
            reply_markup=cancel_kb("admin_broadcast"),
            parse_mode="HTML"
        )
    elif target == "username":
        await state.set_state(Broadcast.target_value)
        await safe_edit(callback, 
            "👤 Введи <b>@username</b> (без @):",
            reply_markup=cancel_kb("admin_broadcast"),
            parse_mode="HTML"
        )
    elif target == "id":
        await state.set_state(Broadcast.target_value)
        await safe_edit(callback, 
            "🆔 Введи <b>ID</b> пользователя:",
            reply_markup=cancel_kb("admin_broadcast"),
            parse_mode="HTML"
        )
    await callback.answer()


@router.message(Broadcast.target_value)
async def broadcast_target_value(message: Message, state: FSMContext):
    await state.update_data(target_value=message.text.strip())
    await state.set_state(Broadcast.input_text)
    await message.answer(
        "📝 Введи текст сообщения (поддерживается HTML):",
        reply_markup=cancel_kb("admin_broadcast")
    )


@router.message(Broadcast.input_text)
async def broadcast_text(message: Message, state: FSMContext):
    await state.update_data(text=message.html_text or message.text)
    await state.set_state(Broadcast.add_media)
    await message.answer(
        "🖼 Отправь <b>фото или видео</b> для прикрепления (или напиши 'пропустить'):",
        reply_markup=InlineKeyboardBuilder().row(
            InlineKeyboardButton(text="⏩ Пропустить", callback_data="broadcast_skip_media")
        ).row(
            InlineKeyboardButton(text="❌ Отмена", callback_data="admin_broadcast")
        ).as_markup(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "broadcast_skip_media")
async def broadcast_skip_media(callback: CallbackQuery, state: FSMContext):
    await state.update_data(media_type=None, media_file_id=None)
    await state.set_state(Broadcast.add_buttons)
    await safe_edit(callback, 
        "🔘 Добавь кнопки в формате:\n"
        "<code>Текст кнопки - https://ссылка.ру</code>\n"
        "По одной кнопке на строку. Или напиши 'пропустить':",
        reply_markup=InlineKeyboardBuilder().row(
            InlineKeyboardButton(text="⏩ Пропустить", callback_data="broadcast_skip_buttons")
        ).row(
            InlineKeyboardButton(text="❌ Отмена", callback_data="admin_broadcast")
        ).as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(Broadcast.add_media)
async def broadcast_media(message: Message, state: FSMContext):
    media_type = None
    file_id = None

    if message.photo:
        media_type = "photo"
        file_id = message.photo[-1].file_id
    elif message.video:
        media_type = "video"
        file_id = message.video.file_id
    elif message.text and message.text.lower() == "пропустить":
        pass
    else:
        await message.answer("❌ Отправь фото, видео или напиши 'пропустить'")
        return

    await state.update_data(media_type=media_type, media_file_id=file_id)
    await state.set_state(Broadcast.add_buttons)
    await message.answer(
        "🔘 Добавь кнопки в формате:\n"
        "<code>Текст кнопки - https://ссылка.ру</code>\n"
        "По одной кнопке на строку. Или напиши 'пропустить':",
        reply_markup=InlineKeyboardBuilder().row(
            InlineKeyboardButton(text="⏩ Пропустить", callback_data="broadcast_skip_buttons")
        ).row(
            InlineKeyboardButton(text="❌ Отмена", callback_data="admin_broadcast")
        ).as_markup(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "broadcast_skip_buttons")
async def broadcast_skip_buttons(callback: CallbackQuery, state: FSMContext):
    await state.update_data(buttons_raw=None)
    await _show_broadcast_preview(callback.message, state)
    await callback.answer()


@router.message(Broadcast.add_buttons)
async def broadcast_buttons(message: Message, state: FSMContext):
    if message.text and message.text.lower() != "пропустить":
        await state.update_data(buttons_raw=message.text)
    else:
        await state.update_data(buttons_raw=None)

    await _show_broadcast_preview(message, state)


async def _build_broadcast_keyboard(buttons_raw: str = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if buttons_raw:
        for line in buttons_raw.strip().split("\n"):
            if " - " in line:
                parts = line.split(" - ", 1)
                text = parts[0].strip()
                url = parts[1].strip()
                builder.row(InlineKeyboardButton(text=text, url=url))
    builder.row(InlineKeyboardButton(text="✅ Отправить", callback_data="broadcast_confirm"))
    builder.row(InlineKeyboardButton(text="✏️ Редактировать", callback_data="broadcast_edit"))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="admin_broadcast"))
    return builder.as_markup()


async def _show_broadcast_preview(target, state: FSMContext):
    data = await state.get_data()
    text = (
        f"📢 <b>Предпросмотр рассылки</b>\n\n"
        f"<b>Тип:</b> {data['target_type']}\n"
        f"<b>Цель:</b> {data['target_value']}\n\n"
        f"{data['text']}"
    )

    kb = await _build_broadcast_keyboard(data.get('buttons_raw'))

    await state.set_state(Broadcast.preview)

    if data.get('media_type') == "photo" and data.get('media_file_id'):
        if hasattr(target, 'answer_photo'):
            await target.answer_photo(data['media_file_id'], caption=text, reply_markup=kb, parse_mode="HTML")
        else:
            await target.edit_text(text, reply_markup=kb, parse_mode="HTML")
    elif data.get('media_type') == "video" and data.get('media_file_id'):
        if hasattr(target, 'answer_video'):
            await target.answer_video(data['media_file_id'], caption=text, reply_markup=kb, parse_mode="HTML")
        else:
            await target.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        if hasattr(target, 'edit_text'):
            await target.edit_text(text, reply_markup=kb, parse_mode="HTML")
        else:
            await target.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "broadcast_edit")
async def broadcast_edit(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Broadcast.input_text)
    await safe_edit(callback, 
        "✏️ Введи новый текст сообщения:",
        reply_markup=cancel_kb("admin_broadcast"),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "broadcast_confirm")
async def broadcast_confirm(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    target_type = data['target_type']
    target_value = data['target_value']
    text = data['text']
    media_type = data.get('media_type')
    media_id = data.get('media_file_id')
    buttons_raw = data.get('buttons_raw')

    # Собираем кнопки
    buttons = []
    if buttons_raw:
        for line in buttons_raw.strip().split("\n"):
            if " - " in line:
                parts = line.split(" - ", 1)
                buttons.append({"text": parts[0].strip(), "url": parts[1].strip()})

    # Определяем получателей
    recipients = []
    if target_type == "all":
        recipients = await get_all_user_ids()
    elif target_type == "id":
        try:
            recipients = [int(target_value)]
        except ValueError:
            await callback.answer("Неверный ID", show_alert=True)
            return
    elif target_type == "username":
        # Ищем по username
        from database import aiosqlite, DB_PATH
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute(
                "SELECT user_id FROM users WHERE username = ?",
                (target_value.lstrip("@"),)
            )
            row = await cur.fetchone()
            if row:
                recipients = [row[0]]
            else:
                await callback.answer("Пользователь не найден", show_alert=True)
                return

    # Создаём клавиатуру для сообщения
    msg_kb = None
    if buttons:
        b = InlineKeyboardBuilder()
        for btn in buttons:
            b.row(InlineKeyboardButton(text=btn['text'], url=btn['url']))
        msg_kb = b.as_markup()

    sent = 0
    failed = 0

    for user_id in recipients:
        try:
            if media_type == "photo" and media_id:
                await bot.send_photo(user_id, media_id, caption=text, reply_markup=msg_kb, parse_mode="HTML")
            elif media_type == "video" and media_id:
                await bot.send_video(user_id, media_id, caption=text, reply_markup=msg_kb, parse_mode="HTML")
            else:
                await bot.send_message(user_id, text, reply_markup=msg_kb, parse_mode="HTML", disable_web_page_preview=True)
            sent += 1
        except Exception:
            failed += 1

    await log_broadcast(
        callback.from_user.id, target_type, target_value,
        text, media_type or "", media_id or "",
        json.dumps(buttons), sent, failed
    )

    await state.clear()
    await safe_edit(callback, 
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"📤 Отправлено: <b>{sent}</b>\n"
        f"❌ Ошибок: <b>{failed}</b>",
        reply_markup=admin_broadcast_kb(),
        parse_mode="HTML"
    )
    await callback.answer(f"Отправлено: {sent}")


# ═════════════════════════════════════════════════════════
#  СТРИМЕРЫ (партнёрская программа)
# ═════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin_streamers")
async def admin_streamers(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.clear()
    first_pct, repeat_pct = await get_streamer_percents()
    min_withdraw = await get_streamer_min_withdraw()
    await safe_edit(callback,
        "🎥 <b>Управление стримерами</b>\n\n"
        "Стримерский промокод даёт зрителю скидку на кейс или пополнение, "
        "а самому стримеру — процент со всех покупок привлечённых им зрителей "
        "(с первой покупки — один процент, дальше — другой, пониже).\n\n"
        f"📊 Текущие условия:\n"
        f"• Первая покупка зрителя: <b>{first_pct}%</b>\n"
        f"• Последующие покупки: <b>{repeat_pct}%</b>\n"
        f"• Минимальный вывод: <b>{min_withdraw}₽</b>",
        reply_markup=admin_streamers_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


# ─── Добавить стримера ───────────────────────────────────

@router.callback_query(F.data == "admin_streamer_add")
async def admin_streamer_add_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminStreamerAdd.streamer_user_id)
    await safe_edit(callback,
        "➕ <b>Новый стример</b>\n\n"
        "Пришли Telegram ID стримера (числом). Это ID пользователя, "
        "который уже писал боту хотя бы раз (например, узнать можно через "
        "@userinfobot или из его сообщений в саппорт):",
        reply_markup=cancel_kb("admin_streamers"),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminStreamerAdd.streamer_user_id)
async def admin_streamer_add_uid(message: Message, state: FSMContext):
    try:
        streamer_uid = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введи числовой Telegram ID.")
        return

    existing = await get_streamer_by_user(streamer_uid)
    if existing:
        await message.answer(
            f"❌ У пользователя <code>{streamer_uid}</code> уже есть промокод "
            f"(<code>{existing['promo_id']}</code>). Сначала удали его в списке стримеров.",
            parse_mode="HTML"
        )
        return

    await state.update_data(streamer_user_id=streamer_uid)
    await state.set_state(AdminStreamerAdd.code)
    await message.answer(
        "🎟 Введи промокод для стримера (например, <code>STREAMERNAME</code>):",
        reply_markup=cancel_kb("admin_streamers"),
        parse_mode="HTML"
    )


@router.message(AdminStreamerAdd.code)
async def admin_streamer_add_code(message: Message, state: FSMContext):
    code = message.text.strip().upper()
    if not code or " " in code:
        await message.answer("❌ Код не должен содержать пробелов. Попробуй ещё раз:")
        return

    existing = await get_promocode_by_code(code)
    if existing:
        await message.answer(
            f"❌ Промокод <code>{code}</code> уже существует. Введи другой код:",
            parse_mode="HTML"
        )
        return

    await state.update_data(code=code)
    await state.set_state(AdminStreamerAdd.promo_type)
    await message.answer(
        "🏷 Какую скидку получает зритель по этому промокоду?",
        reply_markup=streamer_promo_type_kb()
    )


@router.callback_query(F.data.startswith("spromo_type:"))
async def admin_streamer_promo_type(callback: CallbackQuery, state: FSMContext):
    promo_type = callback.data.split(":")[1]
    await state.update_data(promo_type=promo_type, case_id=None)

    if promo_type == "case":
        cases = await get_cases(active_only=False)
        await state.set_state(AdminStreamerAdd.case_select)
        await safe_edit(callback,
            "🎲 На какой кейс распространяется скидка?",
            reply_markup=streamer_promo_case_select_kb(cases),
            parse_mode="HTML"
        )
    else:
        await state.set_state(AdminStreamerAdd.discount)
        await safe_edit(callback,
            "💯 Введи размер скидки зрителю в процентах (например, <code>10</code>):",
            reply_markup=cancel_kb("admin_streamers"),
            parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data.startswith("spromo_case:"))
async def admin_streamer_promo_case_select(callback: CallbackQuery, state: FSMContext):
    value = callback.data.split(":", 1)[1]
    case_id = None if value == "all" else int(value)
    await state.update_data(case_id=case_id)
    await state.set_state(AdminStreamerAdd.discount)
    await safe_edit(callback,
        "💯 Введи размер скидки зрителю в процентах (например, <code>15</code>):",
        reply_markup=cancel_kb("admin_streamers"),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminStreamerAdd.discount)
async def admin_streamer_add_discount(message: Message, state: FSMContext):
    try:
        discount = float(message.text.replace(",", ".").replace("%", "").strip())
    except ValueError:
        await message.answer("❌ Введи число, например 10")
        return

    if discount <= 0 or discount > 100:
        await message.answer("❌ Скидка должна быть от 1 до 100")
        return

    await state.update_data(discount=discount)
    data = await state.get_data()
    await state.set_state(AdminStreamerAdd.confirm)

    type_label = "💰 Скидка на пополнение" if data['promo_type'] == 'deposit' else "🎲 Скидка на открытие кейса"
    scope_label = ""
    if data['promo_type'] == 'case':
        if data.get('case_id'):
            case = await get_case(data['case_id'])
            scope_label = f"\n🎯 Кейс: <b>{case['name'] if case else '?'}</b>"
        else:
            scope_label = "\n🎯 Кейс: <b>все кейсы</b>"

    first_pct, repeat_pct = await get_streamer_percents()

    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="✅ Создать", callback_data="streamer_confirm_create"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="admin_streamers")
    )

    await message.answer(
        f"🎥 <b>Проверь перед созданием:</b>\n\n"
        f"👤 Стример: <code>{data['streamer_user_id']}</code>\n"
        f"🎟 Код: <code>{data['code']}</code>\n"
        f"🏷 Тип: {type_label}{scope_label}\n"
        f"💯 Скидка зрителю: <b>{discount}%</b>\n\n"
        f"💰 Комиссия стримеру: {first_pct}% с первой покупки, {repeat_pct}% с последующих\n"
        f"(проценты общие для всех стримеров, меняются в разделе «Настройки»).\n\n"
        f"Создать?",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "streamer_confirm_create")
async def admin_streamer_confirm_create(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    data = await state.get_data()
    promo_id = await create_promocode(
        code=data['code'],
        promo_type=data['promo_type'],
        discount_percent=data['discount'],
        case_id=data.get('case_id'),
        max_uses=None,
        streamer_owner_id=data['streamer_user_id']
    )
    await create_streamer(user_id=data['streamer_user_id'], promo_id=promo_id)
    await state.clear()

    await safe_edit(callback,
        f"✅ Стример <code>{data['streamer_user_id']}</code> добавлен!\n"
        f"🎟 Промокод: <code>{data['code']}</code>",
        reply_markup=admin_streamers_kb(),
        parse_mode="HTML"
    )
    await callback.answer("Стример добавлен!")

    try:
        await callback.bot.send_message(
            data['streamer_user_id'],
            f"🎥 <b>Вы подключены как стример KeyRush!</b>\n\n"
            f"🎟 Ваш промокод: <code>{data['code']}</code>\n\n"
            f"Загляните во вкладку «🎥 Стримерам» в главном меню — там ваш "
            f"личный кабинет с балансом, условиями и выводом средств.",
            parse_mode="HTML"
        )
    except Exception:
        pass


# ─── Список стримеров ────────────────────────────────────

@router.callback_query(F.data == "admin_streamer_list")
async def admin_streamer_list(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    streamers = await get_all_streamers()
    if not streamers:
        await safe_edit(callback,
            "😕 Стримеров пока нет.",
            reply_markup=admin_streamers_kb(),
            parse_mode="HTML"
        )
        await callback.answer()
        return

    await safe_edit(callback,
        "🎥 <b>Список стримеров:</b>",
        reply_markup=admin_streamer_list_kb(streamers),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_streamer_view:"))
async def admin_streamer_view(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    user_id = int(callback.data.split(":")[1])
    streamer = await get_streamer_by_user(user_id)
    if not streamer:
        await callback.answer("Стример не найден", show_alert=True)
        return

    customers = await count_streamer_customers(user_id)
    type_label = "💰 Скидка на пополнение" if streamer['promo_type'] == 'deposit' else "🎲 Скидка на открытие кейса"

    text = (
        f"🎥 <b>Стример {user_id}</b>\n\n"
        f"🎟 Код: <code>{streamer['code']}</code>\n"
        f"🏷 Тип: {type_label}\n"
        f"💯 Скидка зрителю: <b>{streamer['discount_percent']}%</b>\n\n"
        f"💰 Баланс к выводу: <b>{streamer['balance_rub']}₽</b>\n"
        f"📈 Всего заработано: <b>{streamer['total_earned_rub']}₽</b>\n"
        f"👥 Привлечено зрителей: <b>{customers}</b>\n"
        f"💳 Реквизиты: <code>{streamer['requisites'] or 'не указаны'}</code>"
    )

    await safe_edit(callback, text, reply_markup=admin_streamer_view_kb(user_id), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("admin_streamer_del:"))
async def admin_streamer_del(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    user_id = int(callback.data.split(":")[1])
    await delete_streamer(user_id)
    await safe_edit(callback,
        "🗑 Стример и его промокод удалены.",
        reply_markup=admin_streamers_kb(),
        parse_mode="HTML"
    )
    await callback.answer("Удалено")


# ─── Заявки на вывод ──────────────────────────────────────

@router.callback_query(F.data == "admin_streamer_payouts")
async def admin_streamer_payouts(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    payouts = await get_streamer_payouts(status="pending")
    if not payouts:
        await safe_edit(callback,
            "😕 Нет активных заявок на вывод.",
            reply_markup=admin_streamers_kb(),
            parse_mode="HTML"
        )
        await callback.answer()
        return

    await safe_edit(callback,
        "💸 <b>Заявки на вывод (в ожидании):</b>",
        reply_markup=admin_streamer_payouts_kb(payouts),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_streamer_payout_view:"))
async def admin_streamer_payout_view(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    payout_id = int(callback.data.split(":")[1])
    payout = await get_streamer_payout(payout_id)
    if not payout:
        await callback.answer("Заявка не найдена", show_alert=True)
        return

    status_label = {"pending": "⏳ В ожидании", "paid": "✅ Выплачено", "rejected": "❌ Отклонено"}.get(
        payout['status'], payout['status']
    )

    text = (
        f"💸 <b>Заявка №{payout['payout_id']}</b>\n\n"
        f"👤 Стример: <code>{payout['streamer_id']}</code>\n"
        f"💰 Сумма: <b>{payout['amount']}₽</b>\n"
        f"💳 Реквизиты: <code>{payout['requisites'] or '—'}</code>\n"
        f"📊 Статус: {status_label}\n"
        f"🕐 Создана: {payout['created_at']}"
    )

    kb = admin_streamer_payout_actions_kb(payout_id) if payout['status'] == 'pending' else None
    if kb is None:
        b = InlineKeyboardBuilder()
        b.row(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_streamer_payouts"))
        kb = b.as_markup()

    await safe_edit(callback, text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("admin_streamer_payout_paid:"))
async def admin_streamer_payout_paid(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    payout_id = int(callback.data.split(":")[1])
    payout = await get_streamer_payout(payout_id)
    if not payout or payout['status'] != 'pending':
        await callback.answer("Заявка уже обработана", show_alert=True)
        return

    await set_streamer_payout_status(payout_id, "paid")

    try:
        await callback.bot.send_message(
            payout['streamer_id'],
            f"✅ <b>Выплата произведена!</b>\n\n💰 Сумма: <b>{payout['amount']}₽</b> отправлена на ваши реквизиты.",
            parse_mode="HTML"
        )
    except Exception:
        pass

    await safe_edit(callback,
        f"✅ Заявка №{payout_id} отмечена как выплаченная.",
        reply_markup=admin_streamers_kb(),
        parse_mode="HTML"
    )
    await callback.answer("Отмечено как выплачено")


@router.callback_query(F.data.startswith("admin_streamer_payout_reject:"))
async def admin_streamer_payout_reject(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    payout_id = int(callback.data.split(":")[1])
    payout = await get_streamer_payout(payout_id)
    if not payout or payout['status'] != 'pending':
        await callback.answer("Заявка уже обработана", show_alert=True)
        return

    # Возвращаем зарезервированную сумму обратно на баланс стримера.
    await update_streamer_balance(payout['streamer_id'], payout['amount'])
    await set_streamer_payout_status(payout_id, "rejected")

    try:
        await callback.bot.send_message(
            payout['streamer_id'],
            f"❌ <b>Заявка на вывод отклонена</b>\n\n"
            f"💰 Сумма <b>{payout['amount']}₽</b> возвращена на ваш баланс. "
            f"Свяжитесь с поддержкой, если это ошибка.",
            parse_mode="HTML"
        )
    except Exception:
        pass

    await safe_edit(callback,
        f"❌ Заявка №{payout_id} отклонена, сумма возвращена стримеру.",
        reply_markup=admin_streamers_kb(),
        parse_mode="HTML"
    )
    await callback.answer("Отклонено")


# ─── Настройки процентов и минимального вывода ───────────

@router.callback_query(F.data == "admin_streamer_settings")
async def admin_streamer_settings(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.clear()
    first_pct, repeat_pct = await get_streamer_percents()
    min_withdraw = await get_streamer_min_withdraw()
    await safe_edit(callback,
        f"⚙️ <b>Настройки стримеров</b>\n\n"
        f"• Процент с первой покупки зрителя: <b>{first_pct}%</b>\n"
        f"• Процент с последующих покупок: <b>{repeat_pct}%</b>\n"
        f"• Минимальная сумма вывода: <b>{min_withdraw}₽</b>\n\n"
        f"Эти значения применяются сразу ко всем стримерам.",
        reply_markup=admin_streamer_settings_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin_sset_first")
async def admin_sset_first_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminStreamerSettings.first_pct)
    await safe_edit(callback,
        "✏️ Введи новый процент с первой покупки зрителя (например, <code>10</code>):",
        reply_markup=cancel_kb("admin_streamer_settings"),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminStreamerSettings.first_pct)
async def admin_sset_first_save(message: Message, state: FSMContext):
    try:
        value = float(message.text.replace(",", ".").replace("%", "").strip())
        if not (0 < value <= 100):
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи число от 0 до 100")
        return
    await set_setting("streamer_first_pct", str(value))
    await state.clear()
    await message.answer(f"✅ Процент с первой покупки установлен: {value}%", reply_markup=admin_streamer_settings_kb())


@router.callback_query(F.data == "admin_sset_repeat")
async def admin_sset_repeat_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminStreamerSettings.repeat_pct)
    await safe_edit(callback,
        "✏️ Введи новый процент с последующих покупок (например, <code>5</code>):",
        reply_markup=cancel_kb("admin_streamer_settings"),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminStreamerSettings.repeat_pct)
async def admin_sset_repeat_save(message: Message, state: FSMContext):
    try:
        value = float(message.text.replace(",", ".").replace("%", "").strip())
        if not (0 < value <= 100):
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи число от 0 до 100")
        return
    await set_setting("streamer_repeat_pct", str(value))
    await state.clear()
    await message.answer(f"✅ Процент с последующих покупок установлен: {value}%", reply_markup=admin_streamer_settings_kb())


@router.callback_query(F.data == "admin_sset_minw")
async def admin_sset_minw_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminStreamerSettings.min_withdraw)
    await safe_edit(callback,
        "✏️ Введи новую минимальную сумму вывода в рублях (например, <code>1000</code>):",
        reply_markup=cancel_kb("admin_streamer_settings"),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminStreamerSettings.min_withdraw)
async def admin_sset_minw_save(message: Message, state: FSMContext):
    try:
        value = int(message.text.strip())
        if value <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи целое положительное число")
        return
    await set_setting("streamer_min_withdraw", str(value))
    await state.clear()
    await message.answer(f"✅ Минимальная сумма вывода установлена: {value}₽", reply_markup=admin_streamer_settings_kb())


# ═════════════════════════════════════════════════════════
#  НАЧИСЛЕНИЕ БАЛАНСА ПОЛЬЗОВАТЕЛЮ
# ═════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin_credit_balance")
async def admin_credit_balance_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminCreditBalance.user_id)
    await safe_edit(callback,
        "💰 <b>Начисление баланса</b>\n\n"
        "Пришли Telegram ID пользователя, которому нужно начислить (или списать) баланс:",
        reply_markup=cancel_kb("admin_panel"),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminCreditBalance.user_id)
async def admin_credit_balance_uid(message: Message, state: FSMContext):
    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введи числовой Telegram ID.")
        return

    user = await get_user(user_id)
    if not user:
        await message.answer(
            "❌ Пользователь с таким ID не найден в базе (он должен хотя бы раз запустить бота)."
        )
        return

    await state.update_data(user_id=user_id)
    await state.set_state(AdminCreditBalance.amount)
    await message.answer(
        f"👤 Пользователь найден. Текущий баланс: <b>{user['balance_rub']}₽</b>\n\n"
        f"💵 Введи сумму для начисления в рублях.\n"
        f"Можно с минусом, чтобы списать (например, <code>-100</code>):",
        reply_markup=cancel_kb("admin_panel"),
        parse_mode="HTML"
    )


@router.message(AdminCreditBalance.amount)
async def admin_credit_balance_amount(message: Message, state: FSMContext):
    try:
        amount = int(message.text.replace("+", "").strip())
    except ValueError:
        await message.answer("❌ Введи целое число, например 500 или -100")
        return

    if amount == 0:
        await message.answer("❌ Сумма не может быть равна 0")
        return

    data = await state.get_data()
    user_id = data['user_id']
    user = await get_user(user_id)
    if not user:
        await state.clear()
        await message.answer("❌ Пользователь пропал из базы, начни заново.")
        return

    await state.update_data(amount=amount)
    await state.set_state(AdminCreditBalance.confirm)

    action_label = "начислить" if amount > 0 else "списать"
    new_balance = user['balance_rub'] + amount

    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="✅ Подтвердить", callback_data="credit_balance_confirm"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="admin_panel")
    )

    await message.answer(
        f"⚠️ <b>Подтверди операцию:</b>\n\n"
        f"👤 Пользователь: <code>{user_id}</code>\n"
        f"💰 Текущий баланс: {user['balance_rub']}₽\n"
        f"{'➕' if amount > 0 else '➖'} {action_label.capitalize()}: <b>{abs(amount)}₽</b>\n"
        f"📊 Новый баланс: <b>{new_balance}₽</b>",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "credit_balance_confirm")
async def admin_credit_balance_confirm(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    data = await state.get_data()
    user_id = data.get('user_id')
    amount = data.get('amount')
    await state.clear()

    if user_id is None or amount is None:
        await callback.answer("Сессия истекла, начни заново", show_alert=True)
        return

    await update_user_balance(user_id, amount)
    user = await get_user(user_id)

    await safe_edit(callback,
        f"✅ Готово! {'Начислено' if amount > 0 else 'Списано'} <b>{abs(amount)}₽</b> "
        f"пользователю <code>{user_id}</code>.\n"
        f"📊 Новый баланс: <b>{user['balance_rub']}₽</b>",
        reply_markup=admin_panel_kb(await is_admin_log_enabled()),
        parse_mode="HTML"
    )
    await callback.answer("Готово")

    try:
        if amount > 0:
            await callback.bot.send_message(
                user_id,
                f"💰 <b>Твой баланс пополнен администратором!</b>\n\n➕ Начислено: <b>{amount}₽</b>",
                parse_mode="HTML"
            )
        else:
            await callback.bot.send_message(
                user_id,
                f"⚠️ <b>Изменение баланса</b>\n\nСписано: <b>{abs(amount)}₽</b>",
                parse_mode="HTML"
            )
    except Exception:
        pass
