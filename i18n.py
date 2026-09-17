"""
KeyRush i18n — мультиязычность
"""
import json
import os
from typing import Dict

# Загружаем все локали
LOCALES: Dict[str, Dict[str, str]] = {}

_locales_dir = os.path.join(os.path.dirname(__file__), "..", "locales")
for fname in os.listdir(_locales_dir):
    if fname.endswith(".json"):
        lang = fname.replace(".json", "")
        with open(os.path.join(_locales_dir, fname), "r", encoding="utf-8") as f:
            LOCALES[lang] = json.load(f)


def t(lang: str, key: str, **kwargs) -> str:
    """Перевод строки. Если язык не найден — fallback на ru."""
    text = LOCALES.get(lang, LOCALES.get("ru", {})).get(key, key)
    return text.format(**kwargs)


def get_currency_symbol(currency: str) -> str:
    return {"RUB": "₽", "UAH": "₴", "USD": "$"}.get(currency, "₽")
