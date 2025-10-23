from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def rating_kb(step: str):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⭐1", callback_data=f"{step}:1"),
        InlineKeyboardButton(text="⭐2", callback_data=f"{step}:2"),
        InlineKeyboardButton(text="⭐3", callback_data=f"{step}:3"),
        InlineKeyboardButton(text="⭐4", callback_data=f"{step}:4"),
        InlineKeyboardButton(text="⭐5", callback_data=f"{step}:5"),
    ]])

def start_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Начать", callback_data="start_feedback"),
        InlineKeyboardButton(text="Правила акции", callback_data="rules")
    ]])

def manager_kb(fid: int):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Принято", callback_data=f"accept:{fid}")
    ]])

def prize_kb(code: str):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Показать код", callback_data=f"show:{code}"),
        InlineKeyboardButton(text="Условия", callback_data="terms")
    ]])
