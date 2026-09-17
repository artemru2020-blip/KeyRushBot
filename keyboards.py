"""
KeyRush Keyboards
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from services.i18n import t


def main_menu_kb(lang: str = "ru", is_admin: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=t(lang, "menu_cases"), callback_data="menu_cases"),
        InlineKeyboardButton(text=t(lang, "menu_deposit"), callback_data="menu_deposit")
    )
    builder.row(
        InlineKeyboardButton(text=t(lang, "menu_bonus"), callback_data="menu_bonus"),
        InlineKeyboardButton(text=t(lang, "menu_profile"), callback_data="menu_profile")
    )
    builder.row(
        InlineKeyboardButton(text=t(lang, "menu_inventory"), callback_data="menu_inventory"),
        InlineKeyboardButton(text=t(lang, "menu_redeem"), callback_data="menu_redeem")
    )
    builder.row(
        InlineKeyboardButton(text=t(lang, "menu_promo"), callback_data="menu_promo"),
        InlineKeyboardButton(text="🌐 Язык / Language", callback_data="menu_lang")
    )
    builder.row(
        InlineKeyboardButton(text=t(lang, "menu_referral"), callback_data="menu_referral"),
        InlineKeyboardButton(text=t(lang, "menu_streamers"), callback_data="menu_streamers")
    )
    builder.row(
        InlineKeyboardButton(text="🌍 Global channel", url="https://t.me/KeyRushChannel"),
        InlineKeyboardButton(text="🌐 CIS channel", url="https://t.me/KeyRush_CIS_Channel")
    )
    if is_admin:
        builder.row(
            InlineKeyboardButton(text=t(lang, "admin_panel"), callback_data="admin_panel")
        )
    return builder.as_markup()


def cases_list_kb(cases: list, lang: str = "ru", currency_symbol: str = "₽") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for case in cases:
        builder.row(InlineKeyboardButton(
            text=f"🎲 {case['name']} — {case['price']}{currency_symbol}",
            callback_data=f"case_open:{case['case_id']}"
        ))
    builder.row(InlineKeyboardButton(text=t(lang, "back"), callback_data="main_menu"))
    return builder.as_markup()


def case_confirm_kb(case_id: int, price: int, lang: str = "ru", currency_symbol: str = "₽") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=t(lang, "open_for", price=price, currency=currency_symbol), callback_data=f"case_confirm:{case_id}"),
        InlineKeyboardButton(text=t(lang, "back"), callback_data="menu_cases")
    )
    return builder.as_markup()


def case_result_kb(lang: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=t(lang, "open_more"), callback_data="menu_cases"),
        InlineKeyboardButton(text=t(lang, "home"), callback_data="main_menu")
    )
    return builder.as_markup()


def deposit_kb(lang: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="₿ CryptoBot", callback_data="deposit:crypto")
    )
    builder.row(
        InlineKeyboardButton(text="💳 YooKassa", callback_data="deposit:yookassa")
    )
    builder.row(
        InlineKeyboardButton(text="⭐ Telegram Stars", callback_data="deposit:stars")
    )
    builder.row(
        InlineKeyboardButton(text=t(lang, "back"), callback_data="main_menu")
    )
    return builder.as_markup()


def deposit_pay_kb(provider: str, ref: str, url: str = None, lang: str = "ru") -> InlineKeyboardMarkup:
    """
    ref — идентификатор конкретного счета/платежа у провайдера
    (invoice_id для CryptoBot, payment.id для ЮKassa), а НЕ сумма.
    Это нужно, чтобы при проверке статуса запросить именно этот платеж у API,
    а не просто "поверить" пользователю на слово.
    """
    builder = InlineKeyboardBuilder()
    if url:
        builder.row(InlineKeyboardButton(text=t(lang, "go_to_payment"), url=url))
    builder.row(
        InlineKeyboardButton(text=t(lang, "i_paid"), callback_data=f"deposit_check:{provider}:{ref}")
    )
    builder.row(
        InlineKeyboardButton(text=t(lang, "cancel"), callback_data="menu_deposit")
    )
    return builder.as_markup()


def bonus_kb(can_take: bool, lang: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if can_take:
        builder.row(InlineKeyboardButton(text=t(lang, "get_bonus"), callback_data="bonus_take"))
    else:
        builder.row(InlineKeyboardButton(text=t(lang, "refresh"), callback_data="menu_bonus"))
    builder.row(InlineKeyboardButton(text=t(lang, "back"), callback_data="main_menu"))
    return builder.as_markup()


def lang_kb(lang: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru"),
        InlineKeyboardButton(text="🇺🇦 Українська", callback_data="lang:ua")
    )
    builder.row(
        InlineKeyboardButton(text="🇬🇧 English", callback_data="lang:en")
    )
    builder.row(
        InlineKeyboardButton(text=t(lang, "back"), callback_data="main_menu")
    )
    return builder.as_markup()


def admin_panel_kb(log_enabled: bool = True) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📦 Кейсы", callback_data="admin_cases"),
        InlineKeyboardButton(text="🎁 Призы", callback_data="admin_prizes")
    )
    builder.row(
        InlineKeyboardButton(text="📊 Экономика", callback_data="admin_economy"),
        InlineKeyboardButton(text="📈 Статистика", callback_data="admin_stats")
    )
    builder.row(
        InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast"),
        InlineKeyboardButton(text="🔑 Ключи", callback_data="admin_keys")
    )
    builder.row(
        InlineKeyboardButton(text="🎟 Промокоды", callback_data="admin_promo"),
        InlineKeyboardButton(text="🎥 Стримеры", callback_data="admin_streamers")
    )
    builder.row(
        InlineKeyboardButton(text="💰 Начислить баланс", callback_data="admin_credit_balance")
    )
    builder.row(
        InlineKeyboardButton(
            text=f"🔔 Лог в чат: {'ВКЛ ✅' if log_enabled else 'ВЫКЛ ⛔️'}",
            callback_data="admin_log_toggle"
        )
    )
    builder.row(
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
    )
    return builder.as_markup()


# ─── Промокоды ───────────────────────────────────────────

def admin_promo_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Добавить промокод", callback_data="admin_promo_add")
    )
    builder.row(
        InlineKeyboardButton(text="📋 Список промокодов", callback_data="admin_promo_list")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Админ-панель", callback_data="admin_panel")
    )
    return builder.as_markup()


def promo_type_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💰 Скидка на пополнение", callback_data="promo_type:deposit")
    )
    builder.row(
        InlineKeyboardButton(text="🎲 Скидка на открытие кейса", callback_data="promo_type:case")
    )
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="admin_promo"))
    return builder.as_markup()


def promo_case_select_kb(cases: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🌐 Все кейсы", callback_data="promo_case:all")
    )
    for case in cases:
        builder.row(InlineKeyboardButton(
            text=f"🎲 {case['name']}",
            callback_data=f"promo_case:{case['case_id']}"
        ))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="admin_promo"))
    return builder.as_markup()


def promo_max_uses_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="♾ Без ограничения", callback_data="promo_unlimited"))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="admin_promo"))
    return builder.as_markup()


def promo_list_kb(promos: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for p in promos:
        status = "🟢" if p['is_active'] else "🔴"
        builder.row(InlineKeyboardButton(
            text=f"{status} {p['code']}",
            callback_data=f"admin_promo_view:{p['promo_id']}"
        ))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_promo"))
    return builder.as_markup()


def promo_actions_kb(promo_id: int, is_active: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    toggle_text = "⛔️ Деактивировать" if is_active else "✅ Активировать"
    builder.row(InlineKeyboardButton(text=toggle_text, callback_data=f"admin_promo_toggle:{promo_id}"))
    builder.row(InlineKeyboardButton(text="🗑 Удалить", callback_data=f"admin_promo_del:{promo_id}"))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_promo_list"))
    return builder.as_markup()


def admin_stats_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_stats"))
    builder.row(InlineKeyboardButton(text="🔙 Админ-панель", callback_data="admin_panel"))
    return builder.as_markup()


def admin_cases_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Добавить кейс", callback_data="admin_case_add")
    )
    builder.row(
        InlineKeyboardButton(text="📋 Список кейсов", callback_data="admin_case_list")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Админ-панель", callback_data="admin_panel")
    )
    return builder.as_markup()


def admin_case_actions_kb(case_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"admin_case_edit_menu:{case_id}")
    )
    builder.row(
        InlineKeyboardButton(text="🎁 Настроить призы", callback_data=f"admin_case_prizes:{case_id}")
    )
    builder.row(
        InlineKeyboardButton(text="🗑 Удалить кейс", callback_data=f"admin_case_del:{case_id}")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="admin_case_list")
    )
    return builder.as_markup()


def admin_case_edit_menu_kb(case_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✏️ Название", callback_data=f"acedit_name:{case_id}"),
        InlineKeyboardButton(text="📝 Описание", callback_data=f"acedit_desc:{case_id}")
    )
    builder.row(
        InlineKeyboardButton(text="💰 Цена", callback_data=f"acedit_price:{case_id}"),
        InlineKeyboardButton(text="🖼 Изображение", callback_data=f"acedit_image:{case_id}")
    )
    builder.row(
        InlineKeyboardButton(text="🗑 Убрать изображение", callback_data=f"acedit_image_del:{case_id}")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data=f"admin_case_edit:{case_id}")
    )
    return builder.as_markup()


def admin_prizes_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Добавить приз", callback_data="admin_prize_add")
    )
    builder.row(
        InlineKeyboardButton(text="📋 Список призов", callback_data="admin_prize_list")
    )
    builder.row(
        InlineKeyboardButton(text="🗑 Удалить приз", callback_data="admin_prize_del_list")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Админ-панель", callback_data="admin_panel")
    )
    return builder.as_markup()


def admin_prize_list_kb(prizes: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for p in prizes:
        builder.row(InlineKeyboardButton(
            text=f"⚙️ {p['game_name']} ({p['rarity']})",
            callback_data=f"admin_prize_edit:{p['prize_id']}"
        ))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_prizes"))
    return builder.as_markup()


def admin_prize_actions_kb(prize_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"admin_prize_edit_menu:{prize_id}")
    )
    builder.row(
        InlineKeyboardButton(text="🗑 Удалить приз", callback_data=f"admin_prize_del:{prize_id}")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="admin_prize_list")
    )
    return builder.as_markup()


def admin_prize_edit_menu_kb(prize_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✏️ Название", callback_data=f"apedit_name:{prize_id}"),
        InlineKeyboardButton(text="📝 Описание", callback_data=f"apedit_desc:{prize_id}")
    )
    builder.row(
        InlineKeyboardButton(text="🖼 Изображение", callback_data=f"apedit_image:{prize_id}")
    )
    builder.row(
        InlineKeyboardButton(text="🗑 Убрать изображение", callback_data=f"apedit_image_del:{prize_id}")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data=f"admin_prize_edit:{prize_id}")
    )
    return builder.as_markup()


def admin_prize_delete_list_kb(prizes: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for p in prizes:
        builder.row(InlineKeyboardButton(
            text=f"🗑 {p['game_name']} ({p['rarity']})",
            callback_data=f"admin_prize_del:{p['prize_id']}"
        ))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_prizes"))
    return builder.as_markup()


def admin_prize_delete_confirm_kb(prize_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"admin_prize_del_confirm:{prize_id}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="admin_prize_del_list")
    )
    return builder.as_markup()


def admin_keys_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Добавить ключи", callback_data="admin_keys_add")
    )
    builder.row(
        InlineKeyboardButton(text="🗑 Удалить ключи", callback_data="admin_keys_del")
    )
    builder.row(
        InlineKeyboardButton(text="📦 Инвентарь", callback_data="admin_keys_inv")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Админ-панель", callback_data="admin_panel")
    )
    return builder.as_markup()


def admin_broadcast_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👤 По username", callback_data="broadcast:username")
    )
    builder.row(
        InlineKeyboardButton(text="🆔 По ID", callback_data="broadcast:id")
    )
    builder.row(
        InlineKeyboardButton(text="📢 Всем", callback_data="broadcast:all")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Админ-панель", callback_data="admin_panel")
    )
    return builder.as_markup()


def cancel_kb(back_to: str = "admin_panel", lang: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=t(lang, "cancel"), callback_data=back_to))
    return builder.as_markup()


def profile_kb(lang: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=t(lang, "menu_cases"), callback_data="menu_cases"),
        InlineKeyboardButton(text=t(lang, "home"), callback_data="main_menu")
    )
    return builder.as_markup()


# ─── Рефералы ──────────────────────────────────────────────

def referral_kb(has_referrer: bool, lang: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if not has_referrer:
        builder.row(InlineKeyboardButton(text=t(lang, "referral_enter_btn"), callback_data="referral_enter"))
    builder.row(InlineKeyboardButton(text=t(lang, "home"), callback_data="main_menu"))
    return builder.as_markup()


# ─── Стримеры ──────────────────────────────────────────────

def streamer_tab_kb(is_streamer: bool, lang: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if is_streamer:
        builder.row(
            InlineKeyboardButton(text=t(lang, "streamer_btn_requisites"), callback_data="streamer_requisites")
        )
        builder.row(
            InlineKeyboardButton(text=t(lang, "streamer_btn_withdraw"), callback_data="streamer_withdraw")
        )
    else:
        builder.row(InlineKeyboardButton(text=t(lang, "streamer_btn_support"), url="https://t.me/KeyRush_support"))
    builder.row(InlineKeyboardButton(text=t(lang, "home"), callback_data="main_menu"))
    return builder.as_markup()


# ─── Админ: Стримеры ─────────────────────────────────────

def admin_streamers_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Добавить стримера", callback_data="admin_streamer_add")
    )
    builder.row(
        InlineKeyboardButton(text="📋 Список стримеров", callback_data="admin_streamer_list")
    )
    builder.row(
        InlineKeyboardButton(text="💸 Заявки на вывод", callback_data="admin_streamer_payouts")
    )
    builder.row(
        InlineKeyboardButton(text="⚙️ Настройки процентов/вывода", callback_data="admin_streamer_settings")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Админ-панель", callback_data="admin_panel")
    )
    return builder.as_markup()


def streamer_promo_type_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💰 Скидка на пополнение", callback_data="spromo_type:deposit")
    )
    builder.row(
        InlineKeyboardButton(text="🎲 Скидка на открытие кейса", callback_data="spromo_type:case")
    )
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="admin_streamers"))
    return builder.as_markup()


def streamer_promo_case_select_kb(cases: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🌐 Все кейсы", callback_data="spromo_case:all")
    )
    for case in cases:
        builder.row(InlineKeyboardButton(
            text=f"🎲 {case['name']}",
            callback_data=f"spromo_case:{case['case_id']}"
        ))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="admin_streamers"))
    return builder.as_markup()


def admin_streamer_list_kb(streamers: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for s in streamers:
        builder.row(InlineKeyboardButton(
            text=f"🎥 {s['code']} · {s['user_id']} · {s['balance_rub']}₽",
            callback_data=f"admin_streamer_view:{s['user_id']}"
        ))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_streamers"))
    return builder.as_markup()


def admin_streamer_view_kb(user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🗑 Удалить стримера", callback_data=f"admin_streamer_del:{user_id}"))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_streamer_list"))
    return builder.as_markup()


def admin_streamer_payouts_kb(payouts: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for p in payouts:
        builder.row(InlineKeyboardButton(
            text=f"💸 #{p['payout_id']} · {p['streamer_id']} · {p['amount']}₽",
            callback_data=f"admin_streamer_payout_view:{p['payout_id']}"
        ))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_streamers"))
    return builder.as_markup()


def admin_streamer_payout_actions_kb(payout_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Выплачено", callback_data=f"admin_streamer_payout_paid:{payout_id}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"admin_streamer_payout_reject:{payout_id}")
    )
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_streamer_payouts"))
    return builder.as_markup()


def admin_streamer_settings_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✏️ % с первой покупки", callback_data="admin_sset_first"))
    builder.row(InlineKeyboardButton(text="✏️ % с последующих покупок", callback_data="admin_sset_repeat"))
    builder.row(InlineKeyboardButton(text="✏️ Мин. сумма вывода", callback_data="admin_sset_minw"))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_streamers"))
    return builder.as_markup()


def inventory_kb(items: list, lang: str = "ru", currency_symbol: str = "₽") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for item in items:
        builder.row(InlineKeyboardButton(
            text=t(lang, "sell_for", game=item['game_name'], price=item['sell_price'], currency=currency_symbol),
            callback_data=f"sell_key:{item['inv_id']}"
        ))
    builder.row(InlineKeyboardButton(text=t(lang, "home"), callback_data="main_menu"))
    return builder.as_markup()
