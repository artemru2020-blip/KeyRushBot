"""
KeyRush FSM States
"""
from aiogram.fsm.state import State, StatesGroup


class AdminCaseAdd(StatesGroup):
    name = State()
    description = State()
    price = State()
    image = State()
    confirm = State()


class AdminPrizeAdd(StatesGroup):
    game_name = State()
    rarity = State()
    market_value = State()
    cost_price = State()
    description = State()
    image = State()
    confirm = State()


class AdminCaseEdit(StatesGroup):
    name = State()
    description = State()
    price = State()
    image = State()


class AdminPrizeEdit(StatesGroup):
    game_name = State()
    description = State()
    image = State()


class AdminKeysAdd(StatesGroup):
    select_prize = State()
    input_keys = State()
    confirm = State()


class AdminKeysDel(StatesGroup):
    select_prize = State()
    input_count = State()
    confirm = State()


class AdminCasePrizes(StatesGroup):
    select_case = State()
    select_prize = State()
    set_weight = State()


class AdminPromoAdd(StatesGroup):
    code = State()
    promo_type = State()
    case_select = State()
    discount = State()
    max_uses = State()
    confirm = State()


class PromoActivate(StatesGroup):
    code = State()


class Broadcast(StatesGroup):
    target_type = State()
    target_value = State()
    input_text = State()
    add_media = State()
    add_buttons = State()
    preview = State()
    confirm = State()


class ReferralActivate(StatesGroup):
    code = State()


class StreamerRequisites(StatesGroup):
    input = State()


class AdminStreamerAdd(StatesGroup):
    streamer_user_id = State()
    code = State()
    promo_type = State()
    case_select = State()
    discount = State()
    confirm = State()


class AdminStreamerSettings(StatesGroup):
    first_pct = State()
    repeat_pct = State()
    min_withdraw = State()


class AdminCreditBalance(StatesGroup):
    user_id = State()
    amount = State()
    confirm = State()


class DepositCustom(StatesGroup):
    # ВАЖНО: у каждого способа оплаты — своё отдельное состояние.
    # Раньше CryptoBot и ЮKassa использовали одно и то же состояние
    # input_amount, из-за чего aiogram всегда вызывал первый
    # зарегистрированный обработчик (CryptoBot) — ветка ЮKassa
    # фактически никогда не срабатывала.
    crypto_amount = State()
    yookassa_amount = State()
    stars_amount = State()
    confirm = State()
