"""
KeyRush Configuration
"""
import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Config:
    # ─── Telegram ──────────────────────────────────────
    BOT_TOKEN: str = "7930977988:AAH0o3R_Mvwd8eKBO1GJw7ZuruH_vVeV3KA"
    ADMIN_IDS: list = field(default_factory=lambda: [7349007935])

    # ─── Payments ──────────────────────────────────────
    CRYPTO_BOT_TOKEN: str = "565838:AAj9Gtn81064SzVOt4bZR5PYFwVFQ5h0QpX"
    YOOKASSA_SHOP_ID: str = "1261869"
    YOOKASSA_SECRET_KEY: str = "live_CmHQshNlXaw3ucPYX0PYsxHUR7EJjCRM3bb8gHCiIvw"

    # ─── Database ──────────────────────────────────────
    DB_PATH: str = "keyrush.db"

    # ─── Media ─────────────────────────────────────────
    START_VIDEO_PATH: str = os.path.join(os.path.dirname(__file__), "media", "start.mp4")

    # ─── Language & Currency ───────────────────────────
    DEFAULT_LANG: str = "ru"
    SUPPORTED_LANGS: list = field(default_factory=lambda: ["ru", "ua", "en"])
    DEFAULT_CURRENCY: str = "RUB"
    SUPPORTED_CURRENCIES: list = field(default_factory=lambda: ["RUB", "UAH", "USD"])
    # Валюта, которая подставляется автоматически при переключении языка.
    LANG_CURRENCY: dict = field(default_factory=lambda: {"ru": "RUB", "ua": "UAH", "en": "USD"})

    # ─── Курсы валют ────────────────────────────────────
    # Внутри бота ВСЕ суммы (баланс, цены кейсов и т.д.) всегда хранятся
    # в рублях. Курс USD/UAH к рублю подтягивается автоматически с сайта
    # ЦБ РФ (см. services/rates.py) и кэшируется на CURRENCY_RATE_TTL секунд,
    # чтобы не дёргать внешний API на каждый показ цены. Пересчёт «рубли ->
    # валюта пользователя» (для отображения) и «валюта пользователя -> рубли»
    # (при вводе суммы пополнения) идёт по этому живому курсу.
    # FALLBACK_RATES используются только если ЦБ временно недоступен —
    # значения ниже стоит время от времени сверять с актуальным курсом.
    CURRENCY_RATE_TTL: int = 6 * 3600
    FALLBACK_RATES: dict = field(default_factory=lambda: {"USD": 90.0, "UAH": 2.2})
    # Минимальная сумма пополнения, в рублёвом эквиваленте (историческое
    # значение — раньше пополнение всегда было только в рублях).
    MIN_DEPOSIT_RUB: int = 30

    # ─── Economy ───────────────────────────────────────
    CASE_PRICE: int = 49
    BASE_KEY_COST: int = 4

    PRIZE_FUND_PCT: float = 0.408
    RESERVE_PCT: float = 0.102
    OPERATING_PCT: float = 0.102
    PROFIT_PCT: float = 0.306
    TARGET_RTP: float = 0.72

    # ─── Points System ─────────────────────────────────
    POINTS_FOR_PREMIUM_KEY: int = 100_000
    DAILY_BONUS_MIN: int = 1
    DAILY_BONUS_MAX: int = 5

    # ─── Sell Back ───────────────────────────────────
    SELL_BACK_RATE: float = 0.70

    # ─── Deposit Bonus ───────────────────────────────
    BONUS_DEPOSIT_RATE: float = 0.25

    # ─── Fake Wins ─────────────────────────────────────
    FAKE_WINS_COUNT: int = 3

    # ─── Telegram Stars ──────────────────────────────
    # У Stars нет своего "курса" в БД — это внутренняя валюта Telegram.
      # STARS_TO_RUB_RATE — сколько рублей баланса начисляется за 1 звезду.
    # Скорректируй под актуальный курс звёзд, если он изменится.
    STARS_TO_RUB_RATE: float = 1.5
    MIN_STARS_DEPOSIT: int = 20

    # ─── Admin live-log (лог событий в чат админа) ─────
    ADMIN_LOG_DEFAULT_ENABLED: bool = True

    # ─── Реферальная система ────────────────────────────
    # Баллы начисляются один раз при первом заходе приглашённого по ссылке
    # или при вводе реферального кода.
    REFERRAL_INVITER_POINTS: int = 500
    REFERRAL_INVITED_POINTS: int = 250

    # ─── Стримеры (партнёрская программа) ───────────────
    # Проценты и минимальная сумма вывода ниже — это значения ПО УМОЛЧАНИЮ.
    # Реальные значения хранятся в таблице settings и могут быть изменены
    # администратором прямо из бота (Админ-панель → Стримеры → Настройки),
    # без правки кода.
    STREAMER_FIRST_PURCHASE_PCT: float = 10.0   # % с первой покупки приглашённого зрителя
    STREAMER_REPEAT_PURCHASE_PCT: float = 5.0   # % со всех последующих покупок
    STREAMER_MIN_WITHDRAW: int = 1000           # минимальная сумма вывода, ₽


cfg = Config()
