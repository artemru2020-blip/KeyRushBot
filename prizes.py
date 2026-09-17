"""
KeyRush Prize Logic
"""
import random
from typing import List, Dict


def weighted_choice(prizes: List[Dict]) -> Dict:
    """
    Выбирает приз по весам.
    prizes: список словарей с ключом 'weight'
    """
    total = sum(p['weight'] for p in prizes)
    r = random.uniform(0, total)
    cumulative = 0
    for p in prizes:
        cumulative += p['weight']
        if r <= cumulative:
            return p
    return prizes[-1]
