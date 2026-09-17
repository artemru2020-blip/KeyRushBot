"""
KeyRush Database Layer
"""
import aiosqlite
import json
import random
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from config import cfg

DB_PATH = cfg.DB_PATH


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                balance_rub INTEGER DEFAULT 0,
                language TEXT DEFAULT 'ru',
                currency TEXT DEFAULT 'RUB',
                points INTEGER DEFAULT 0,
                total_opens INTEGER DEFAULT 0,
                total_spent INTEGER DEFAULT 0,
                total_won_market INTEGER DEFAULT 0,
                total_won_cost INTEGER DEFAULT 0,
                last_bonus_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                banned INTEGER DEFAULT 0
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS cases (
                case_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                price INTEGER NOT NULL,
                image_url TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS prizes (
                prize_id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_name TEXT NOT NULL,
                description TEXT,
                image_url TEXT,
                rarity TEXT DEFAULT 'common',
                market_value INTEGER DEFAULT 0,
                cost_price INTEGER DEFAULT 0,
                total_keys INTEGER DEFAULT 0,
                available_keys INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS case_prizes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                prize_id INTEGER NOT NULL,
                weight REAL NOT NULL DEFAULT 1.0,
                UNIQUE(case_id, prize_id),
                FOREIGN KEY (case_id) REFERENCES cases(case_id),
                FOREIGN KEY (prize_id) REFERENCES prizes(prize_id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS keys_inventory (
                key_id INTEGER PRIMARY KEY AUTOINCREMENT,
                prize_id INTEGER NOT NULL,
                steam_key TEXT NOT NULL UNIQUE,
                status TEXT DEFAULT 'available',
                used_at TEXT,
                used_by INTEGER,
                FOREIGN KEY (prize_id) REFERENCES prizes(prize_id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_inventory (
                inv_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                prize_id INTEGER NOT NULL,
                key_id INTEGER NOT NULL,
                game_name TEXT NOT NULL,
                steam_key TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                sell_price INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (prize_id) REFERENCES prizes(prize_id),
                FOREIGN KEY (key_id) REFERENCES keys_inventory(key_id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS opens (
                open_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                case_id INTEGER NOT NULL,
                prize_id INTEGER NOT NULL,
                key_id INTEGER,
                price_paid INTEGER NOT NULL,
                prize_cost INTEGER NOT NULL,
                prize_market_value INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS ledger (
                tx_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                type TEXT NOT NULL,
                amount INTEGER NOT NULL,
                currency TEXT DEFAULT 'RUB',
                case_id INTEGER,
                prize_id INTEGER,
                description TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS funds (
                fund_id INTEGER PRIMARY KEY AUTOINCREMENT,
                fund_name TEXT NOT NULL UNIQUE,
                amount INTEGER DEFAULT 0,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS daily_bonus_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                points_given INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS broadcast_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER NOT NULL,
                target_type TEXT NOT NULL,
                target_value TEXT,
                message_text TEXT,
                media_type TEXT,
                media_file_id TEXT,
                buttons_json TEXT,
                sent_count INTEGER DEFAULT 0,
                fail_count INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS fake_wins_pool (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                display_name TEXT NOT NULL,
                game_name TEXT NOT NULL,
                is_premium INTEGER DEFAULT 0
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS deposits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                provider TEXT NOT NULL,
                provider_ref TEXT NOT NULL,
                amount INTEGER NOT NULL,
                bonus_points INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                credited_at TEXT,
                UNIQUE(provider, provider_ref)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS daily_top_win (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL UNIQUE,
                game_name TEXT NOT NULL,
                user_display TEXT,
                is_fake INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ─── Промокоды ───────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS promocodes (
                promo_id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                promo_type TEXT NOT NULL,          -- 'deposit' или 'case'
                discount_percent REAL NOT NULL,
                case_id INTEGER,                    -- NULL = действует на все кейсы (только для типа 'case')
                max_uses INTEGER,                   -- NULL = без ограничения
                used_count INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (case_id) REFERENCES cases(case_id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS promo_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                promo_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                used_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(promo_id, user_id)
            )
        """)

        # Миграция: добавляем колонку active_promo_id в users, если её ещё нет
        # (для баз, созданных до появления системы промокодов).
        try:
            await db.execute("ALTER TABLE users ADD COLUMN active_promo_id INTEGER")
        except aiosqlite.OperationalError:
            pass

        # ─── Рефералы и стримеры: миграции колонок users/promocodes ──
        try:
            await db.execute("ALTER TABLE users ADD COLUMN referred_by INTEGER")
        except aiosqlite.OperationalError:
            pass
        try:
            # К какому стримеру привязан пользователь (для расчёта комиссии
            # с его покупок). Проставляется один раз — при первой активации
            # стримерского промокода — и больше не меняется.
            await db.execute("ALTER TABLE users ADD COLUMN attributed_streamer_id INTEGER")
        except aiosqlite.OperationalError:
            pass
        try:
            # NULL — обычный промокод админа. Иначе — user_id стримера,
            # которому принадлежит этот код и который получает с него комиссию.
            await db.execute("ALTER TABLE promocodes ADD COLUMN streamer_owner_id INTEGER")
        except aiosqlite.OperationalError:
            pass

        # ─── Редактирование призов: добавляем описание и картинку ────
        # (для баз, созданных до появления редактирования призов).
        try:
            await db.execute("ALTER TABLE prizes ADD COLUMN description TEXT")
        except aiosqlite.OperationalError:
            pass
        try:
            await db.execute("ALTER TABLE prizes ADD COLUMN image_url TEXT")
        except aiosqlite.OperationalError:
            pass

        # ─── Стримеры (партнёрская программа) ────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS streamers (
                user_id INTEGER PRIMARY KEY,
                promo_id INTEGER NOT NULL,
                balance_rub INTEGER DEFAULT 0,
                total_earned_rub INTEGER DEFAULT 0,
                requisites TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (promo_id) REFERENCES promocodes(promo_id)
            )
        """)

        # Счётчик покупок каждого приглашённого зрителя у конкретного
        # стримера — нужен, чтобы понять "это первая покупка или нет"
        # для расчёта процента комиссии.
        await db.execute("""
            CREATE TABLE IF NOT EXISTS streamer_customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                streamer_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                purchases_count INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(streamer_id, user_id)
            )
        """)

        # Лог начислений стримерам — для прозрачности и истории.
        await db.execute("""
            CREATE TABLE IF NOT EXISTS streamer_earnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                streamer_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                source TEXT NOT NULL,
                purchase_amount INTEGER NOT NULL,
                percent REAL NOT NULL,
                earned_rub INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Заявки на вывод средств стримеров.
        await db.execute("""
            CREATE TABLE IF NOT EXISTS streamer_payouts (
                payout_id INTEGER PRIMARY KEY AUTOINCREMENT,
                streamer_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                requisites TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                processed_at TEXT
            )
        """)

        for fund in ['revenue', 'prize_fund', 'reserve', 'operating', 'profit', 'available']:
            await db.execute("""
                INSERT OR IGNORE INTO funds (fund_name, amount) VALUES (?, 0)
            """, (fund,))

        await db.commit()


# ─── Users ───────────────────────────────────────────────

async def get_or_create_user(user_id: int, username: str = None, full_name: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        is_new = False
        if not row:
            is_new = True
            await db.execute("""
                INSERT INTO users (user_id, username, full_name, language, currency)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, username, full_name, cfg.DEFAULT_LANG, cfg.DEFAULT_CURRENCY))
            await db.commit()
            cur = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = await cur.fetchone()
        elif username is not None or full_name is not None:
            # Подтягиваем актуальные username/full_name, если они изменились в Telegram
            await db.execute(
                "UPDATE users SET username = COALESCE(?, username), full_name = COALESCE(?, full_name) WHERE user_id = ?",
                (username, full_name, user_id)
            )
            await db.commit()
        user = dict(row)
        user['_is_new'] = is_new
        return user


async def update_user_balance(user_id: int, amount_rub: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE users SET balance_rub = balance_rub + ? WHERE user_id = ?
        """, (amount_rub, user_id))
        await db.commit()


async def create_pending_deposit(user_id: int, provider: str, provider_ref: str, amount: int, bonus_points: int) -> bool:
    """Регистрирует ожидающий депозит. Возвращает False, если такой provider_ref уже существует."""
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute("""
                INSERT INTO deposits (user_id, provider, provider_ref, amount, bonus_points, status)
                VALUES (?, ?, ?, ?, ?, 'pending')
            """, (user_id, provider, str(provider_ref), amount, bonus_points))
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False


async def get_deposit(provider: str, provider_ref: str) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM deposits WHERE provider = ? AND provider_ref = ?",
            (provider, str(provider_ref))
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def claim_deposit_credit(provider: str, provider_ref: str) -> Optional[Dict]:
    """
    Атомарно переводит депозит pending -> credited и возвращает его данные,
    либо None, если депозита нет или он уже был зачислен (защита от повторного начисления
    при повторных нажатиях кнопки "Я оплатил" или гонках).
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""
            UPDATE deposits
            SET status = 'credited', credited_at = CURRENT_TIMESTAMP
            WHERE provider = ? AND provider_ref = ? AND status = 'pending'
        """, (provider, str(provider_ref)))
        await db.commit()
        if cur.rowcount == 0:
            return None
        cur2 = await db.execute(
            "SELECT * FROM deposits WHERE provider = ? AND provider_ref = ?",
            (provider, str(provider_ref))
        )
        row = await cur2.fetchone()
        return dict(row) if row else None


async def add_points(user_id: int, points: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE users SET points = points + ? WHERE user_id = ?
        """, (points, user_id))
        await db.commit()


async def get_user(user_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


# ─── Cases ───────────────────────────────────────────────

async def create_case(name: str, description: str, price: int, image_url: str = None) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            INSERT INTO cases (name, description, price, image_url)
            VALUES (?, ?, ?, ?)
        """, (name, description, price, image_url))
        await db.commit()
        return cur.lastrowid


async def get_cases(active_only: bool = True) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        sql = "SELECT * FROM cases"
        if active_only:
            sql += " WHERE is_active = 1"
        cur = await db.execute(sql)
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_case(case_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def delete_case(case_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM case_prizes WHERE case_id = ?", (case_id,))
        await db.execute("DELETE FROM cases WHERE case_id = ?", (case_id,))
        await db.commit()


async def update_case(case_id: int, **fields) -> None:
    """Частичное обновление кейса: передавай только те поля, которые
    меняются, например update_case(case_id, name='Новое имя')."""
    allowed = {"name", "description", "price", "image_url"}
    fields = {k: v for k, v in fields.items() if k in allowed}
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [case_id]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE cases SET {set_clause} WHERE case_id = ?", values)
        await db.commit()


# ─── Prizes & Keys ───────────────────────────────────────

async def create_prize(game_name: str, rarity: str, market_value: int, cost_price: int,
                        description: str = None, image_url: str = None) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            INSERT INTO prizes (game_name, rarity, market_value, cost_price, description, image_url)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (game_name, rarity, market_value, cost_price, description, image_url))
        await db.commit()
        return cur.lastrowid


async def update_prize(prize_id: int, **fields) -> None:
    """Частичное обновление приза: передавай только те поля, которые
    меняются, например update_prize(prize_id, game_name='Новое имя')."""
    allowed = {"game_name", "description", "image_url", "rarity", "market_value", "cost_price"}
    fields = {k: v for k, v in fields.items() if k in allowed}
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [prize_id]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE prizes SET {set_clause} WHERE prize_id = ?", values)
        await db.commit()


async def get_prizes() -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM prizes")
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def set_user_language(user_id: int, lang: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET language = ? WHERE user_id = ?", (lang, user_id))
        await db.commit()

async def set_user_currency(user_id: int, currency: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET currency = ? WHERE user_id = ?", (currency, user_id))
        await db.commit()

async def get_user_language(user_id: int) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        return row[0] if row else cfg.DEFAULT_LANG

async def get_user_currency(user_id: int) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT currency FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        return row[0] if row else cfg.DEFAULT_CURRENCY

async def get_prize(prize_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM prizes WHERE prize_id = ?", (prize_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def delete_prize(prize_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM case_prizes WHERE prize_id = ?", (prize_id,))
        await db.execute("DELETE FROM keys_inventory WHERE prize_id = ?", (prize_id,))
        await db.execute("DELETE FROM prizes WHERE prize_id = ?", (prize_id,))
        await db.commit()


async def add_keys_to_prize(prize_id: int, keys: List[str]):
    async with aiosqlite.connect(DB_PATH) as db:
        for key in keys:
            try:
                await db.execute("""
                    INSERT INTO keys_inventory (prize_id, steam_key) VALUES (?, ?)
                """, (prize_id, key.strip()))
            except aiosqlite.IntegrityError:
                pass
        await db.execute("""
            UPDATE prizes 
            SET total_keys = total_keys + ?, available_keys = available_keys + ?
            WHERE prize_id = ?
        """, (len(keys), len(keys), prize_id))
        await db.commit()


async def remove_keys_from_prize(prize_id: int, count: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT key_id FROM keys_inventory 
            WHERE prize_id = ? AND status = 'available'
            LIMIT ?
        """, (prize_id, count))
        rows = await cur.fetchall()
        removed = len(rows)
        for (key_id,) in rows:
            await db.execute("DELETE FROM keys_inventory WHERE key_id = ?", (key_id,))
        await db.execute("""
            UPDATE prizes 
            SET total_keys = total_keys - ?, available_keys = available_keys - ?
            WHERE prize_id = ?
        """, (removed, removed, prize_id))
        await db.commit()
        return removed


async def get_available_key(prize_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""
            SELECT * FROM keys_inventory 
            WHERE prize_id = ? AND status = 'available'
            LIMIT 1
        """, (prize_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def mark_key_used(key_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE keys_inventory 
            SET status = 'used', used_at = datetime('now'), used_by = ?
            WHERE key_id = ?
        """, (user_id, key_id))
        await db.execute("""
            UPDATE prizes SET available_keys = available_keys - 1 WHERE prize_id = (
                SELECT prize_id FROM keys_inventory WHERE key_id = ?
            )
        """, (key_id,))
        await db.commit()


# ─── Case Prizes (weights) ───────────────────────────────

async def set_case_prize(case_id: int, prize_id: int, weight: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO case_prizes (case_id, prize_id, weight)
            VALUES (?, ?, ?)
            ON CONFLICT(case_id, prize_id) DO UPDATE SET weight = excluded.weight
        """, (case_id, prize_id, weight))
        await db.commit()


async def get_case_prizes(case_id: int) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""
            SELECT cp.*, p.game_name, p.rarity, p.market_value, p.cost_price, p.available_keys
            FROM case_prizes cp
            JOIN prizes p ON cp.prize_id = p.prize_id
            WHERE cp.case_id = ?
        """, (case_id,))
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def remove_case_prize(case_id: int, prize_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            DELETE FROM case_prizes WHERE case_id = ? AND prize_id = ?
        """, (case_id, prize_id))
        await db.commit()


# ─── Opens ───────────────────────────────────────────────

async def record_open(user_id: int, case_id: int, prize_id: int, key_id: Optional[int],
                      price_paid: int, prize_cost: int, prize_market_value: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            INSERT INTO opens (user_id, case_id, prize_id, key_id, price_paid, prize_cost, prize_market_value)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, case_id, prize_id, key_id, price_paid, prize_cost, prize_market_value))
        await db.execute("""
            UPDATE users 
            SET total_opens = total_opens + 1, total_spent = total_spent + ?,
                total_won_market = total_won_market + ?,
                total_won_cost = total_won_cost + ?
            WHERE user_id = ?
        """, (price_paid, prize_market_value, prize_cost, user_id))
        await db.commit()
        return cur.lastrowid


# ─── Ledger & Funds ──────────────────────────────────────

async def add_ledger_entry(user_id: Optional[int], type_: str, amount: int,
                           case_id: Optional[int] = None, prize_id: Optional[int] = None,
                           description: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO ledger (user_id, type, amount, case_id, prize_id, description)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, type_, amount, case_id, prize_id, description))
        await db.commit()


async def get_fund(fund_name: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT amount FROM funds WHERE fund_name = ?", (fund_name,))
        row = await cur.fetchone()
        return row[0] if row else 0


async def update_fund(fund_name: str, delta: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE funds SET amount = amount + ?, updated_at = datetime('now')
            WHERE fund_name = ?
        """, (delta, fund_name))
        await db.commit()


async def get_economy_stats() -> Dict[str, Any]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        cur = await db.execute("SELECT COALESCE(SUM(amount),0) FROM ledger WHERE type='payment'")
        revenue = (await cur.fetchone())[0]

        cur = await db.execute("SELECT COUNT(*) FROM opens")
        total_opens = (await cur.fetchone())[0]

        cur = await db.execute("SELECT COALESCE(SUM(prize_cost),0) FROM opens")
        total_cost = (await cur.fetchone())[0]

        avg_cost = total_cost / total_opens if total_opens else 0

        funds = {}
        for name in ['revenue', 'prize_fund', 'reserve', 'operating', 'profit', 'available']:
            cur = await db.execute("SELECT amount FROM funds WHERE fund_name = ?", (name,))
            funds[name] = (await cur.fetchone())[0]

        cur = await db.execute("SELECT COALESCE(SUM(price_paid),0) FROM opens")
        total_paid = (await cur.fetchone())[0]
        rtp = (total_cost / total_paid * 100) if total_paid else 0
        margin = 100 - rtp

        return {
            'revenue': revenue,
            'total_opens': total_opens,
            'total_cost': total_cost,
            'avg_prize_cost': round(avg_cost, 2),
            'rtp': round(rtp, 1),
            'margin': round(margin, 1),
            'funds': funds
        }


# ─── Daily Bonus ─────────────────────────────────────────

async def can_take_bonus(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT created_at FROM daily_bonus_log 
            WHERE user_id = ? ORDER BY id DESC LIMIT 1
        """, (user_id,))
        row = await cur.fetchone()
        if not row:
            return True
        last = datetime.fromisoformat(row[0])
        now = datetime.now()
        return (now - last).total_seconds() >= 20 * 3600


async def log_bonus(user_id: int, points: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO daily_bonus_log (user_id, points_given) VALUES (?, ?)
        """, (user_id, points))
        await db.commit()


async def get_last_bonus_time(user_id: int) -> Optional[datetime]:
    """Возвращает время последнего полученного бонуса или None, если бонус ещё не брали."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT created_at FROM daily_bonus_log
            WHERE user_id = ? ORDER BY id DESC LIMIT 1
        """, (user_id,))
        row = await cur.fetchone()
        if not row:
            return None
        return datetime.fromisoformat(row[0])


# ─── Fake Wins ───────────────────────────────────────────

async def seed_fake_wins():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM fake_wins_pool")
        if (await cur.fetchone())[0] > 0:
            return

        cheap = [
            "SEXY CHRISTMAS", "Ship of Love", "Alien Cat", "Cute Cats 3",
            "WET GIRLS", "Burn, Clown, Burn!", "Cute Dogs",
            "Hentai Shooter 3D: Christmas Party", "Gabenwood: 99 Hidden Bucks",
            "Achievement Clicker", "Zup!", "Zup! 2", "Zup! 3", "Zup! Zero",
            "Pixel Puzzles: UndeadZ", "Pixel Puzzles 2: Anime",
            "Absconding Zatwor", "Break Into Zatwor", "Fiends of Imprisonment",
            "They Came From The Moon", "GooCubelets", "GooCubelets 2",
            "GooCubelets: The Algoorithm", "Overcast", "Overcast 2",
            "Woodle Tree Adventures", "Woodle Tree 2: Worlds",
            "Graveyard Shift", "Cyberpunk 3776", "Neon Hardcorps",
            "Space Pilgrim Episode I", "Space Pilgrim Episode II",
            "Space Pilgrim Episode III", "Space Pilgrim Episode IV",
            "Data Hacker: Initiation", "Data Hacker: Corruption",
            "Data Hacker: Reboot", "Invasion", "Invasion 2",
            "Not Without My Poop", "Sleengster", "Sleengster 2",
            "Torch Cave", "Torch Cave 2", "Bob The Cube",
            "Barbarian", "Barbarian 2", "Blood of Old",
            "Crab Cakes Rescue", "Clergy Splode", "Clergy Splode 2",
            "Dead6hot", "Desert Thunder", "Devil Share",
            "Elements II: Hearts of Light", "Elements: Soul of Fire",
            "Er-Spectro", "Freebie", "Gnumz: Masters of Defense",
            "Heaven Island Life", "Heaven Island - VR MMO", "High on Racing",
            "HotLead", "Hyper color ball", "iBomber Defense Pacific",
            "Journey To The Center Of The Earth", "Krog Wars", "Labyrinth",
            "Lawnmower Game", "Lawnmower Game 2", "Lawnmower Game 3",
            "Lawnmower Game 4", "Little Adventures", "Lucky Panda", "Lup",
            "Masked Shooters 2", "Masked Forces", "Masked Shooters",
            "Maya", "Mini Golf", "Mumps", "Nosferatu: The Wrath of Malachi",
            "Particula", "Pester", "Plazma Being", "Press X to Not Die",
            "ProtoGalaxy", "Radical Roach", "Radical Roach Deluxe",
            "Rage Parking Simulator 2016", "Red Lake", "Rover Rescue",
            "Rush Bros", "Rush for Glory", "Sapper", "Scourge: Outbreak",
            "Shadows of War", "Shiplord", "Shot Shot Tactic", "Sinister City",
            "Sky Mercenaries", "Slipstream 5000", "SoulCraft", "Space Beret",
            "Space Farmer", "Space Moth DX", "Space Pilgrim",
            "Spakoyno: Back to the USSR 2.0", "Sparkle 2 Evo", "Sparkle 3 Genesis",
            "Star Chronicles: Delta Quadrant", "Star Drifter", "Star Fields",
            "Starion Tactics", "Starship Nova Strike", "Steel & Steam: Episode 1",
            "Street Racing Syndicate", "Street Warriors Online", "Super Distro",
            "Super Mega Neo Pug", "Super Ubie Island REMIX", "Switch Galaxy Ultra",
            "TAIKU MANSION", "Tales of Destruction", "Tasty Blue", "Tasty Planet",
            "Tasty Planet: Back for Seconds", "Terra Incognita ~ Chapter One",
            "Terra Lander", "The 39 Steps", "The Albino Hunter",
            "The Culling Of The Cows", "The Deer", "The Defenders: The Second Wave",
            "The Dweller", "The Falling Sun", "The God's Chain",
            "The Haunting of Billy", "The I of the Dragon", "The Interview",
            "The Last Hope", "The Last Hope: Trump vs Mafia", "The Next Door",
            "The Nightmare Cooperative", "The Note", "The Orb Chambers",
            "The Orb Chambers II", "The Pit And The Pendulum", "The Plague",
            "The Reject Demon: Toko Chapter 0", "The Slaughtering Grounds",
            "The Strangers", "The Superfluous", "The Tape", "The Troma Project",
            "The Undying Plague", "The Way", "The Whispered World Special Edition",
            "The Wild Eternal", "Theatre of War", "Theatre of War 2: Africa 1943",
            "Theatre of War 3: Korea", "Theatre of War: Kursk + Caen",
        ]

        premium = [
            "Counter-Strike 2", "Dota 2", "Cyberpunk 2077", "GTA V",
            "The Witcher 3", "Elden Ring", "Red Dead Redemption 2",
            "Baldur's Gate 3", "Hades", "Hogwarts Legacy",
            "Starfield", "Marvel's Spider-Man", "God of War",
            "The Last of Us Part I", "Resident Evil 4", "Final Fantasy XVI",
            "Rust", "PUBG", "Terraria", "Stardew Valley",
            "Portal 2", "Among Us", "Fallout 4", "Skyrim",
            "Dark Souls III", "Sekiro", "Ghost of Tsushima",
            "Horizon Zero Dawn", "Death Stranding", "Control",
            "DOOM Eternal", "Wolfenstein II", "Metro Exodus",
            "Disco Elysium", "Outer Wilds", "Subnautica",
            "Satisfactory", "Factorio", "RimWorld",
            "Divinity: Original Sin 2", "Path of Exile", "Warframe",
        ]

        data = []
        for game in cheap:
            data.append((f"ID:{random.randint(100000000, 999999999)}", game, 0))
        for game in premium:
            data.append((f"ID:{random.randint(100000000, 999999999)}", game, 1))

        await db.executemany("""
            INSERT INTO fake_wins_pool (display_name, game_name, is_premium)
            VALUES (?, ?, ?)
        """, data)
        await db.commit()


async def get_random_fake_win(premium_only: bool = False) -> Dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        sql = "SELECT * FROM fake_wins_pool"
        if premium_only:
            sql += " WHERE is_premium = 1"
        sql += " ORDER BY RANDOM() LIMIT 1"
        cur = await db.execute(sql)
        row = await cur.fetchone()
        return dict(row) if row else {}


# ─── Daily Top Win ───────────────────────────────────────

async def get_daily_top_win() -> Optional[Dict]:
    today = date.today().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM daily_top_win WHERE date = ?", (today,)
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def set_daily_top_win(game_name: str, user_display: str, is_fake: int = 1):
    today = date.today().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO daily_top_win (date, game_name, user_display, is_fake)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                game_name = excluded.game_name,
                user_display = excluded.user_display,
                is_fake = excluded.is_fake,
                created_at = datetime('now')
        """, (today, game_name, user_display, is_fake))
        await db.commit()


# ─── User Inventory ──────────────────────────────────────

async def add_to_inventory(user_id: int, prize_id: int, key_id: int, game_name: str, steam_key: str, sell_price: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO user_inventory (user_id, prize_id, key_id, game_name, steam_key, sell_price)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, prize_id, key_id, game_name, steam_key, sell_price))
        await db.commit()


async def get_user_inventory(user_id: int) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""
            SELECT * FROM user_inventory 
            WHERE user_id = ? AND status = 'active'
            ORDER BY created_at DESC
        """, (user_id,))
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def sell_inventory_item(inv_id: int, user_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""
            SELECT * FROM user_inventory 
            WHERE inv_id = ? AND user_id = ? AND status = 'active'
        """, (inv_id, user_id))
        row = await cur.fetchone()
        if not row:
            return None
        item = dict(row)
        await db.execute("UPDATE user_inventory SET status = 'sold_back' WHERE inv_id = ?", (inv_id,))
        await db.execute("UPDATE users SET balance_rub = balance_rub + ? WHERE user_id = ?",
                         (item['sell_price'], user_id))
        # Возвращаем ключ в пул (опционально — удали если не нужно)
        await db.execute("""
            UPDATE keys_inventory SET status = 'available', used_at = NULL, used_by = NULL
            WHERE key_id = ?
        """, (item['key_id'],))
        await db.execute("UPDATE prizes SET available_keys = available_keys + 1 WHERE prize_id = ?",
                         (item['prize_id'],))
        await db.commit()
        return item


# ─── Broadcast ───────────────────────────────────────────

async def log_broadcast(admin_id: int, target_type: str, target_value: str,
                        text: str, media_type: str, media_file_id: str,
                        buttons_json: str, sent: int, fail: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO broadcast_log 
            (admin_id, target_type, target_value, message_text, media_type, media_file_id, buttons_json, sent_count, fail_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (admin_id, target_type, target_value, text, media_type, media_file_id,
              buttons_json, sent, fail))
        await db.commit()


async def get_all_user_ids() -> List[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id FROM users WHERE banned = 0")
        rows = await cur.fetchall()
        return [r[0] for r in rows]


# ─── Settings (key-value, для тумблеров и т.п.) ──────────

async def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = await cur.fetchone()
        return row[0] if row else default


async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (key, value))
        await db.commit()


# ─── Промокоды ───────────────────────────────────────────

async def create_promocode(code: str, promo_type: str, discount_percent: float,
                            case_id: Optional[int] = None, max_uses: Optional[int] = None,
                            streamer_owner_id: Optional[int] = None) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            INSERT INTO promocodes (code, promo_type, discount_percent, case_id, max_uses, streamer_owner_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (code.strip().upper(), promo_type, discount_percent, case_id, max_uses, streamer_owner_id))
        await db.commit()
        return cur.lastrowid


async def get_promocode_by_code(code: str) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM promocodes WHERE code = ?", (code.strip().upper(),))
        row = await cur.fetchone()
        return dict(row) if row else None


async def get_promocode(promo_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM promocodes WHERE promo_id = ?", (promo_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def get_promocodes() -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM promocodes ORDER BY created_at DESC")
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def set_promocode_active(promo_id: int, active: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE promocodes SET is_active = ? WHERE promo_id = ?", (1 if active else 0, promo_id))
        await db.commit()


async def delete_promocode(promo_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM promocodes WHERE promo_id = ?", (promo_id,))
        await db.execute("DELETE FROM promo_usage WHERE promo_id = ?", (promo_id,))
        await db.execute("UPDATE users SET active_promo_id = NULL WHERE active_promo_id = ?", (promo_id,))
        await db.commit()


async def increment_promo_usage(promo_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE promocodes SET used_count = used_count + 1 WHERE promo_id = ?", (promo_id,))
        await db.commit()


async def has_user_used_promo(promo_id: int, user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT 1 FROM promo_usage WHERE promo_id = ? AND user_id = ?", (promo_id, user_id)
        )
        row = await cur.fetchone()
        return row is not None


async def log_promo_usage(promo_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO promo_usage (promo_id, user_id) VALUES (?, ?)", (promo_id, user_id)
            )
        except aiosqlite.IntegrityError:
            pass
        await db.commit()


async def set_user_active_promo(user_id: int, promo_id: Optional[int]):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET active_promo_id = ? WHERE user_id = ?", (promo_id, user_id))
        await db.commit()


async def get_user_active_promo(user_id: int) -> Optional[Dict]:
    """Возвращает активированный (но ещё не применённый) промокод пользователя, если есть."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""
            SELECT p.* FROM users u
            JOIN promocodes p ON u.active_promo_id = p.promo_id
            WHERE u.user_id = ?
        """, (user_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


# ─── Рефералы ──────────────────────────────────────────────

async def get_user_referred_by(user_id: int) -> Optional[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT referred_by FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        return row[0] if row and row[0] is not None else None


async def set_user_referred_by(user_id: int, referrer_id: int) -> bool:
    """Проставляет пригласившего, только если он ещё не был установлен.
    Возвращает True, если запись действительно была сделана (чтобы не
    начислять баллы повторно при повторных вызовах)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "UPDATE users SET referred_by = ? WHERE user_id = ? AND referred_by IS NULL",
            (referrer_id, user_id)
        )
        await db.commit()
        return cur.rowcount > 0


async def count_referrals(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM users WHERE referred_by = ?", (user_id,))
        row = await cur.fetchone()
        return row[0] if row else 0


# ─── Стримеры (партнёрская программа) ────────────────────

async def create_streamer(user_id: int, promo_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO streamers (user_id, promo_id) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET promo_id = excluded.promo_id, is_active = 1
        """, (user_id, promo_id))
        await db.commit()


async def get_streamer_by_user(user_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM streamers WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def get_all_streamers() -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""
            SELECT s.*, p.code, p.promo_type, p.discount_percent, p.case_id
            FROM streamers s JOIN promocodes p ON s.promo_id = p.promo_id
            ORDER BY s.created_at DESC
        """)
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def delete_streamer(user_id: int) -> Optional[int]:
    """Удаляет профиль стримера и его промокод. Возвращает promo_id, если был."""
    streamer = await get_streamer_by_user(user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM streamers WHERE user_id = ?", (user_id,))
        await db.execute("DELETE FROM streamer_customers WHERE streamer_id = ?", (user_id,))
        await db.execute("UPDATE users SET attributed_streamer_id = NULL WHERE attributed_streamer_id = ?", (user_id,))
        await db.commit()
    if streamer:
        await delete_promocode(streamer['promo_id'])
        return streamer['promo_id']
    return None


async def set_streamer_requisites(user_id: int, requisites: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("UPDATE streamers SET requisites = ? WHERE user_id = ?", (requisites, user_id))
        await db.commit()
        return cur.rowcount > 0


async def set_user_attributed_streamer(user_id: int, streamer_id: int) -> bool:
    """Привязывает пользователя к стримеру один раз (если ещё не привязан
    к другому). Возвращает True, если привязка действительно произошла."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "UPDATE users SET attributed_streamer_id = ? WHERE user_id = ? AND attributed_streamer_id IS NULL",
            (streamer_id, user_id)
        )
        await db.commit()
        if cur.rowcount > 0:
            await db.execute("""
                INSERT INTO streamer_customers (streamer_id, user_id) VALUES (?, ?)
                ON CONFLICT(streamer_id, user_id) DO NOTHING
            """, (streamer_id, user_id))
            await db.commit()
            return True
        return False


async def get_user_attributed_streamer(user_id: int) -> Optional[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT attributed_streamer_id FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        return row[0] if row and row[0] is not None else None


async def increment_streamer_customer_purchase(streamer_id: int, user_id: int) -> int:
    """Увеличивает счётчик покупок этого зрителя у стримера и возвращает
    новое значение счётчика (1 = первая покупка, 2+ = последующие)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO streamer_customers (streamer_id, user_id, purchases_count)
            VALUES (?, ?, 1)
            ON CONFLICT(streamer_id, user_id) DO UPDATE SET purchases_count = purchases_count + 1
        """, (streamer_id, user_id))
        await db.commit()
        cur = await db.execute(
            "SELECT purchases_count FROM streamer_customers WHERE streamer_id = ? AND user_id = ?",
            (streamer_id, user_id)
        )
        row = await cur.fetchone()
        return row[0] if row else 1


async def count_streamer_customers(streamer_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT COUNT(*) FROM streamer_customers WHERE streamer_id = ?", (streamer_id,)
        )
        row = await cur.fetchone()
        return row[0] if row else 0


async def update_streamer_balance(user_id: int, delta: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE streamers
            SET balance_rub = balance_rub + ?,
                total_earned_rub = total_earned_rub + CASE WHEN ? > 0 THEN ? ELSE 0 END
            WHERE user_id = ?
        """, (delta, delta, delta, user_id))
        await db.commit()


async def log_streamer_earning(streamer_id: int, user_id: int, source: str,
                                purchase_amount: int, percent: float, earned_rub: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO streamer_earnings (streamer_id, user_id, source, purchase_amount, percent, earned_rub)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (streamer_id, user_id, source, purchase_amount, percent, earned_rub))
        await db.commit()


async def create_streamer_payout(streamer_id: int, amount: int, requisites: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            INSERT INTO streamer_payouts (streamer_id, amount, requisites, status)
            VALUES (?, ?, ?, 'pending')
        """, (streamer_id, amount, requisites))
        await db.commit()
        return cur.lastrowid


async def get_streamer_payouts(status: Optional[str] = None) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if status:
            cur = await db.execute(
                "SELECT * FROM streamer_payouts WHERE status = ? ORDER BY created_at ASC", (status,)
            )
        else:
            cur = await db.execute("SELECT * FROM streamer_payouts ORDER BY created_at DESC")
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_streamer_payout(payout_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM streamer_payouts WHERE payout_id = ?", (payout_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def set_streamer_payout_status(payout_id: int, status: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE streamer_payouts SET status = ?, processed_at = datetime('now') WHERE payout_id = ?
        """, (status, payout_id))
        await db.commit()


# ─── Статистика для админ-панели ─────────────────────────

async def get_user_stats() -> Dict[str, Any]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM users")
        total = (await cur.fetchone())[0]

        cur = await db.execute("SELECT COUNT(*) FROM users WHERE banned = 1")
        banned = (await cur.fetchone())[0]

        cur = await db.execute("SELECT COUNT(*) FROM users WHERE date(created_at) = date('now')")
        new_today = (await cur.fetchone())[0]

        cur = await db.execute("SELECT COUNT(*) FROM users WHERE created_at >= datetime('now', '-7 days')")
        new_week = (await cur.fetchone())[0]

        cur = await db.execute("SELECT COUNT(*) FROM users WHERE created_at >= datetime('now', '-30 days')")
        new_month = (await cur.fetchone())[0]

        cur = await db.execute("SELECT COALESCE(SUM(balance_rub),0) FROM users")
        total_balance = (await cur.fetchone())[0]

        cur = await db.execute("SELECT COUNT(*) FROM users WHERE total_opens > 0")
        active_openers = (await cur.fetchone())[0]

        cur = await db.execute("""
            SELECT COUNT(DISTINCT user_id) FROM opens WHERE created_at >= datetime('now', '-1 day')
        """)
        active_today = (await cur.fetchone())[0]

        cur = await db.execute("""
            SELECT COUNT(DISTINCT user_id) FROM opens WHERE created_at >= datetime('now', '-7 days')
        """)
        active_week = (await cur.fetchone())[0]

        return {
            'total': total,
            'banned': banned,
            'new_today': new_today,
            'new_week': new_week,
            'new_month': new_month,
            'total_balance': total_balance,
            'active_openers': active_openers,
            'active_today': active_today,
            'active_week': active_week,
        }


async def get_case_open_stats() -> Dict[str, Any]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        cur = await db.execute("SELECT COUNT(*) FROM opens")
        total_opens = (await cur.fetchone())[0]

        cur = await db.execute("SELECT COUNT(*) FROM opens WHERE created_at >= datetime('now', '-1 day')")
        opens_today = (await cur.fetchone())[0]

        cur = await db.execute("SELECT COUNT(*) FROM opens WHERE created_at >= datetime('now', '-7 days')")
        opens_week = (await cur.fetchone())[0]

        cur = await db.execute("SELECT COALESCE(SUM(price_paid),0) FROM opens WHERE created_at >= datetime('now', '-1 day')")
        revenue_today = (await cur.fetchone())[0]

        cur = await db.execute("""
            SELECT c.name, COUNT(*) as cnt
            FROM opens o JOIN cases c ON o.case_id = c.case_id
            GROUP BY o.case_id ORDER BY cnt DESC LIMIT 5
        """)
        top_cases = [dict(r) for r in await cur.fetchall()]

        cur = await db.execute("""
            SELECT p.game_name, p.rarity, COUNT(*) as cnt
            FROM opens o JOIN prizes p ON o.prize_id = p.prize_id
            GROUP BY o.prize_id ORDER BY cnt DESC LIMIT 5
        """)
        top_prizes = [dict(r) for r in await cur.fetchall()]

        cur = await db.execute("""
            SELECT o.user_id, u.username, COUNT(*) as cnt
            FROM opens o LEFT JOIN users u ON o.user_id = u.user_id
            GROUP BY o.user_id ORDER BY cnt DESC LIMIT 5
        """)
        top_users = [dict(r) for r in await cur.fetchall()]

        return {
            'total_opens': total_opens,
            'opens_today': opens_today,
            'opens_week': opens_week,
            'revenue_today': revenue_today,
            'top_cases': top_cases,
            'top_prizes': top_prizes,
            'top_users': top_users,
        }
