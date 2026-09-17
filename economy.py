"""
KeyRush Economic Engine
Расчёт RTP, Prize Fund, Reserve, распределение средств
"""
import random
from typing import Dict, List
from config import cfg
from database import (
    add_ledger_entry, update_fund, record_open, get_available_key, mark_key_used,
    get_case_prizes, get_or_create_user, add_points
)


class EconomyEngine:
    """
    Обрабатывает каждое открытие кейса:
    1. Распределяет деньги по фондам
    2. Выбирает приз по весам
    3. Записывает в Ledger
    4. Обновляет статистику
    """

    @staticmethod
    def distribute_open_funds(price: int, prize_cost: int) -> Dict[str, int]:
        """
        Распределяет деньги с одного открытия.
        Возвращает словарь {fund_name: amount}
        """
        # Сначала покрываем себестоимость приза
        remaining = price - prize_cost

        prize_fund = int(remaining * cfg.PRIZE_FUND_PCT)
        reserve = int(remaining * cfg.RESERVE_PCT)
        operating = int(remaining * cfg.OPERATING_PCT)
        profit = remaining - prize_fund - reserve - operating

        return {
            'prize_fund': prize_fund,
            'reserve': reserve,
            'operating': operating,
            'profit': profit,
            'revenue': price,
            'available': profit  # доступно для вывода = прибыль
        }

    @staticmethod
    def calculate_rtp(case_prizes: List[Dict], case_price: int) -> float:
        """
        RTP = Σ(cost_price × нормализованный вес) / price
        """
        total_weight = sum(p['weight'] for p in case_prizes)
        if total_weight == 0 or case_price == 0:
            return 0.0

        ev = sum(p['cost_price'] * (p['weight'] / total_weight) for p in case_prizes)
        return ev / case_price

    @staticmethod
    async def process_open(user_id: int, case_id: int, case_price: int) -> Dict:
        """
        Полный цикл открытия кейса.
        Возвращает результат с информацией о призе.
        """
        # Получаем призы кейса
        prizes = await get_case_prizes(case_id)
        if not prizes:
            raise ValueError("В кейсе нет призов")

        # Проверяем RTP
        rtp = EconomyEngine.calculate_rtp(prizes, case_price)

        # Выбираем приз по весам
        total_weight = sum(p['weight'] for p in prizes)
        r = random.uniform(0, total_weight)
        cumulative = 0
        selected = prizes[0]

        for p in prizes:
            cumulative += p['weight']
            if r <= cumulative:
                selected = p
                break

        # Проверяем наличие ключа
        key_row = await get_available_key(selected['prize_id'])
        if not key_row:
            # Если ключа нет — выдаём базовый дешёвый приз (fallback)
            # Находим приз с минимальной cost_price
            fallback = min(prizes, key=lambda x: x['cost_price'])
            selected = fallback
            key_row = await get_available_key(selected['prize_id'])
            if not key_row:
                raise ValueError("Нет доступных ключей даже для fallback-приза")

        prize_cost = selected['cost_price']
        prize_market = selected['market_value']

        # Распределяем фонды
        distribution = EconomyEngine.distribute_open_funds(case_price, prize_cost)

        # Записываем в Ledger
        await add_ledger_entry(user_id, 'payment', case_price, case_id, None, 'Оплата открытия кейса')
        await add_ledger_entry(user_id, 'prize_cost', -prize_cost, case_id, selected['prize_id'], f'Себестоимость приза {selected["game_name"]}')
        await add_ledger_entry(None, 'prize_fund', distribution['prize_fund'], case_id, None, 'Отчисление в Prize Fund')
        await add_ledger_entry(None, 'reserve', distribution['reserve'], case_id, None, 'Отчисление в Reserve')
        await add_ledger_entry(None, 'operating', distribution['operating'], case_id, None, 'Операционные расходы')
        await add_ledger_entry(None, 'profit', distribution['profit'], case_id, None, 'Прибыль')

        # Обновляем виртуальные фонды
        await update_fund('revenue', distribution['revenue'])
        await update_fund('prize_fund', distribution['prize_fund'])
        await update_fund('reserve', distribution['reserve'])
        await update_fund('operating', distribution['operating'])
        await update_fund('profit', distribution['profit'])
        await update_fund('available', distribution['available'])

        # Помечаем ключ использованным
        await mark_key_used(key_row['key_id'], user_id)

        # Записываем открытие
        await record_open(user_id, case_id, selected['prize_id'], key_row['key_id'],
                         case_price, prize_cost, prize_market)

        # Если это редкий приз — начисляем баллы
        if selected['rarity'] in ['rare', 'epic', 'legendary']:
            bonus_points = {'rare': 50, 'epic': 200, 'legendary': 1000}.get(selected['rarity'], 0)
            await add_points(user_id, bonus_points)

        return {
            'prize': selected,
            'key': key_row['steam_key'],
            'key_id': key_row['key_id'],
            'rtp': round(rtp * 100, 1),
            'distribution': distribution,
            'is_premium': selected['rarity'] in ['epic', 'legendary']
        }


class EconomySimulator:
    """
    Симуляция N открытий для проверки экономики.
    """

    @staticmethod
    def simulate(case_prizes: List[Dict], case_price: int, n: int) -> Dict:
        total_weight = sum(p['weight'] for p in case_prizes)
        results = []
        total_cost = 0
        total_revenue = n * case_price

        for _ in range(n):
            r = random.uniform(0, total_weight)
            cumulative = 0
            selected = case_prizes[0]
            for p in case_prizes:
                cumulative += p['weight']
                if r <= cumulative:
                    selected = p
                    break
            results.append(selected)
            total_cost += selected['cost_price']

        # Статистика по редкостям
        rarity_counts = {}
        for p in case_prizes:
            rarity_counts[p['rarity']] = 0
        for res in results:
            rarity_counts[res['rarity']] = rarity_counts.get(res['rarity'], 0) + 1

        rtp = (total_cost / total_revenue) * 100 if total_revenue else 0
        margin = 100 - rtp

        # Prize Fund накопление
        avg_prize_cost = total_cost / n if n else 0
        remaining_per_open = case_price - avg_prize_cost
        prize_fund_total = int(remaining_per_open * cfg.PRIZE_FUND_PCT * n)

        return {
            'opens': n,
            'revenue': total_revenue,
            'total_prize_cost': total_cost,
            'avg_prize_cost': round(avg_prize_cost, 2),
            'rtp': round(rtp, 1),
            'margin': round(margin, 1),
            'prize_fund_accumulated': prize_fund_total,
            'rarity_distribution': rarity_counts,
            'expensive_prizes_affordable': prize_fund_total // 2000  # сколько призов по 2000₽ можно купить
        }
