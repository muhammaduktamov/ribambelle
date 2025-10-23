from __future__ import annotations
import random
from datetime import datetime, timedelta
from typing import List, Dict

# Базовый пул призов с весами
DEFAULT_PRIZES: List[Dict] = [
    {"key":"coffee","title":"Кофе/чай в подарок","weight":20,"type":"gift"},
    {"key":"dessert","title":"Десерт дня в подарок","weight":20,"type":"gift"},
    {"key":"lemonade","title":"Лимонад 0.3 в подарок","weight":15,"type":"gift"},
    {"key":"disc10","title":"Скидка 10%","weight":15,"type":"discount"},
    {"key":"pizza","title":"Пицца Маргарита (S)","weight":10,"type":"gift"},
    {"key":"kids","title":"Детская анимация (бесплатно)","weight":10,"type":"service"},
    {"key":"disc20","title":"Скидка 20%","weight":5,"type":"discount"},
    {"key":"chef","title":"Сюрприз от шефа","weight":5,"type":"gift"}
]

def weighted_choice(items: List[Dict]) -> Dict:
    total = sum(i["weight"] for i in items)
    r = random.uniform(0, total)
    upto = 0
    for i in items:
        if upto + i["weight"] >= r:
            return i
        upto += i["weight"]
    return items[-1]

def gen_code(prefix: str = "RB-") -> str:
    import secrets, string
    alphabet = string.ascii_uppercase + string.digits
    return prefix + "".join(secrets.choice(alphabet) for _ in range(7))
