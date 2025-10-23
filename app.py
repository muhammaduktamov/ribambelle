from __future__ import annotations
import asyncio, os, hmac, hashlib, csv
from datetime import datetime, timedelta
from typing import Optional

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

from db import get_conn, init_db
from keyboards import rating_kb, start_kb, manager_kb, prize_kb
from prizes import DEFAULT_PRIZES, weighted_choice, gen_code
import os, socket, time
from aiogram import Router, F
from aiogram.types import Message
router = Router()

START_TS = time.time()

@router.message(F.text == "/where")
async def where_am_i(message: Message):
    host = socket.gethostname()
    pid = os.getpid()
    up = int(time.time() - START_TS)
    token_tail = os.getenv("BOT_TOKEN", "")[-6:]  # только хвост токена
    await message.answer(
        f"🤖 Я запущен на: <b>{host}</b>\n"
        f"PID: <code>{pid}</code>\n"
        f"Uptime: {up} сек\n"
        f"Token…{token_tail}"
    )
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
SECRET_KEY = os.getenv("SECRET_KEY", "change_this_secret").encode()
MANAGERS_CHAT_ID = int(os.getenv("MANAGERS_CHAT_ID", "0"))
PROMO_VALID_DAYS = int(os.getenv("PROMO_VALID_DAYS", "30"))
DB_PATH = os.getenv("DB_PATH", "./bot.db")

from aiogram.client.bot import DefaultBotProperties
from aiogram.enums import ParseMode

bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

dp = Dispatcher(storage=MemoryStorage())

conn = get_conn(DB_PATH)
init_db(conn)

# Простая in-memory «память» на процесс для хранения текущего визита пользователя
VISIT_CACHE: dict[str, str] = {}

NEGATIVE_TRIGGERS = ["холод", "солен", "солё", "долго", "волос", "гряз", "невкус", "остыл", "плохо", "хам", "опозд"]

def now_iso() -> str:
    return datetime.utcnow().isoformat()

def sign_visit(visit_id: str) -> str:
    return hmac.new(SECRET_KEY, visit_id.encode(), hashlib.sha256).hexdigest()

def verify_visit(visit_id: str, sign: str) -> bool:
    return hmac.compare_digest(sign_visit(visit_id), (sign or "").lower())

async def ensure_guest(msg: Message):
    with conn:
        conn.execute(
            "INSERT OR IGNORE INTO guests(tg_user_id, username, created_at) VALUES(?,?,?)",
            (msg.from_user.id, msg.from_user.username, now_iso())
        )

async def visit_used(visit_id: str) -> bool:
    row = conn.execute("SELECT 1 FROM feedback WHERE visit_id = ?", (visit_id,)).fetchone()
    return row is not None

async def create_feedback_placeholder(user_id: int, visit_id: str):
    with conn:
        conn.execute(
            "INSERT INTO visits(visit_id, tg_user_id, created_at) VALUES(?,?,?) "
            "ON CONFLICT(visit_id) DO NOTHING",
            (visit_id, user_id, now_iso())
        )

@dp.message(Command("start"))
async def cmd_start(message: Message, command: CommandObject):
    await ensure_guest(message)

    # Deep link format: visit_<VISIT_ID>_<SIGN>
    arg = (command.args or "").strip()
    visit_id = None
    if arg.startswith("visit_"):
        try:
            _, rest = arg.split("visit_", 1)
            parts = rest.split("_")
            visit_id = parts[0]
            sign = parts[1] if len(parts) > 1 else ""
            if not verify_visit(visit_id, sign):
                visit_id = None
        except Exception:
            visit_id = None

    if visit_id:
        if await visit_used(visit_id):
            await message.answer("❗️ По этому визиту отзыв уже был оставлен. Спасибо за участие!")
            return
        await create_feedback_placeholder(message.from_user.id, visit_id)
        await message.answer(
            "👋 Добро пожаловать в <b>Рибамбель</b>! "
            "Оцените визит (1 минута) — и мы разыграем для вас <b>подарок на следующее посещение</b> 🎁",
            reply_markup=start_kb()
        )
        VISIT_CACHE[f"visit_id:{message.from_user.id}"] = visit_id
    else:
        await message.answer(
            "👋 Добро пожаловать в <b>Рибамбель</b>! "
            "Сканируйте QR-код на столе, чтобы участвовать в розыгрыше подарков."
        )

@dp.callback_query(F.data == "rules")
async def cb_rules(c: CallbackQuery):
    await c.answer()
    await c.message.answer(
        "🎯 <b>Правила акции</b>\n"
        "• После короткой оценки вы получаете случайный приз на следующее посещение.\n"
        f"• Промокод действует {PROMO_VALID_DAYS} дней. Один код = один стол.\n"
        "• Не суммируется с другими акциями (если не указано иначе)."
    )

@dp.callback_query(F.data == "start_feedback")
async def cb_start_feedback(c: CallbackQuery):
    await c.answer()
    await c.message.answer("Оцените <b>сервис</b>:", reply_markup=rating_kb("service"))

async def _maybe_alert(feedback_id: int, username: Optional[str], table_hint: str, comment: Optional[str]):
    if MANAGERS_CHAT_ID == 0:
        return

    parts: list[str] = [
        "⚠️ <b>Сигнал гостя</b>",
        f"От: @{username or 'unknown'}"
    ]
    if table_hint:
        parts.append(table_hint)
    if comment:
        parts.append(f"Комментарий: <i>{comment}</i>")
    parts.append(f"ID отзыва: #{feedback_id}")

    text = "\n".join(parts)
    await bot.send_message(MANAGERS_CHAT_ID, text, reply_markup=manager_kb(feedback_id))

def _store_rating(user_id: int, step: str, value: int, visit_id: str):
    row = conn.execute(
        "SELECT id, service, taste, speed, clean FROM feedback WHERE tg_user_id=? AND visit_id=?",
        (user_id, visit_id)
    ).fetchone()
    if row:
        fid = row["id"]
        fields = dict(row)
        fields[step] = value
        with conn:
            conn.execute(f"UPDATE feedback SET {step}=? WHERE id=?", (value, fid))
        return fid, fields
    else:
        with conn:
            conn.execute(
                f"INSERT INTO feedback(tg_user_id, visit_id, created_at, {step}) VALUES(?,?,?,?)",
                (user_id, visit_id, now_iso(), value)
            )
            fid = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        fields = {"service": None, "taste": None, "speed": None, "clean": None}
        fields[step] = value
        return fid, fields

def _low_rating(fields: dict) -> bool:
    vals = [v for v in [fields.get("service"), fields.get("taste"), fields.get("speed"), fields.get("clean")] if v is not None]
    return any(v <= 3 for v in vals)

@dp.callback_query(F.data.startswith("service:"))
async def cb_rate_service(c: CallbackQuery):
    v = int(c.data.split(":")[1])
    visit_id = VISIT_CACHE.get(f"visit_id:{c.from_user.id}", "")
    _store_rating(c.from_user.id, "service", v, visit_id)
    await c.message.edit_text("Оцените <b>вкус блюд</b>:", reply_markup=rating_kb("taste"))

@dp.callback_query(F.data.startswith("taste:"))
async def cb_rate_taste(c: CallbackQuery):
    v = int(c.data.split(":")[1])
    visit_id = VISIT_CACHE.get(f"visit_id:{c.from_user.id}", "")
    _store_rating(c.from_user.id, "taste", v, visit_id)
    await c.message.edit_text("Оцените <b>скорость подачи</b>:", reply_markup=rating_kb("speed"))

@dp.callback_query(F.data.startswith("speed:"))
async def cb_rate_speed(c: CallbackQuery):
    v = int(c.data.split(":")[1])
    visit_id = VISIT_CACHE.get(f"visit_id:{c.from_user.id}", "")
    _store_rating(c.from_user.id, "speed", v, visit_id)
    await c.message.edit_text("Оцените <b>чистоту и атмосферу</b>:", reply_markup=rating_kb("clean"))

@dp.callback_query(F.data.startswith("clean:"))
async def cb_rate_clean(c: CallbackQuery):
    v = int(c.data.split(":")[1])
    visit_id = VISIT_CACHE.get(f"visit_id:{c.from_user.id}", "")
    fid, fields = _store_rating(c.from_user.id, "clean", v, visit_id)

    if _low_rating(fields):
        await c.message.edit_text(
            "Нам важно исправить ситуацию. Позвать менеджера сейчас?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🆘 Позвать менеджера", callback_data=f"callmgr:{fid}"),
                InlineKeyboardButton(text="Нет, продолжить", callback_data=f"cont:{fid}")
            ]])
        )
    else:
        await c.message.edit_text("Оставите короткий комментарий? Напишите сообщением или отправьте «-» чтобы пропустить.")

@dp.callback_query(F.data.startswith("callmgr:"))
async def cb_call_manager(c: CallbackQuery):
    fid = int(c.data.split(":")[1])
    await c.answer("Менеджер уведомлён")

    row = conn.execute("SELECT visit_id FROM feedback WHERE id=?", (fid,)).fetchone()
    table_hint = f"Визит: {row['visit_id']}" if row else ""

    await _maybe_alert(fid, c.from_user.username, table_hint, None)
    with conn:
        conn.execute("UPDATE feedback SET alert_sent=1 WHERE id=?", (fid,))
    await c.message.edit_text("✅ Менеджер уже уведомлён и подойдёт к вам. А пока напишите комментарий, пожалуйста.")

@dp.callback_query(F.data.startswith("cont:"))
async def cb_continue(c: CallbackQuery):
    await c.message.edit_text("Оставите короткий комментарий? Напишите сообщением или отправьте «-» чтобы пропустить.")

@dp.message(F.text)
async def catch_comment(message: Message):
    visit_id = VISIT_CACHE.get(f"visit_id:{message.from_user.id}")
    if not visit_id:
        return

    text = (message.text or "").strip()
    if text == "-":
        text = ""

    row = conn.execute(
        "SELECT id, comment FROM feedback WHERE tg_user_id=? AND visit_id=?",
        (message.from_user.id, visit_id)
    ).fetchone()
    if row:
        fid = row["id"]
        old = row["comment"] or ""
        new = (old + (" " if old and text else "") + text).strip() if text else old
        with conn:
            conn.execute("UPDATE feedback SET comment=? WHERE id=?", (new, fid))

        lowered = (new or "").lower()
        if any(tok in lowered for tok in NEGATIVE_TRIGGERS):
            await _maybe_alert(fid, message.from_user.username, f"Визит: {visit_id}", new)
            with conn:
                conn.execute("UPDATE feedback SET alert_sent=1 WHERE id=?", (fid,))

    await run_prize_flow(message, visit_id)

async def run_prize_flow(message: Message, visit_id: str):
    await message.answer("🎡 Запускаем колесо подарков…")

    prize = weighted_choice(DEFAULT_PRIZES)
    code = gen_code()
    valid_until = (datetime.utcnow() + timedelta(days=PROMO_VALID_DAYS)).isoformat()

    with conn:
        conn.execute(
            """INSERT INTO prizes(code, title, type, valid_until, user_id, visit_id, status, created_at)
               VALUES(?,?,?,?,?,?,?,?)""",
            (code, prize["title"], prize["type"], valid_until, message.from_user.id, visit_id, "issued", now_iso())
        )

    await message.answer(
        "🎉 Вам выпал приз: <b>{title}</b>\n"
        "Ваш промокод: <code>{code}</code>\n"
        "Действует до <b>{date}</b>.\n"
        "Покажите код официанту перед закрытием счёта.".format(
            title=prize["title"],
            code=code,
            date=(datetime.utcnow() + timedelta(days=PROMO_VALID_DAYS)).date().strftime("%d.%m.%Y")
        ),
        reply_markup=prize_kb(code)
    )

    VISIT_CACHE.pop(f"visit_id:{message.from_user.id}", None)

@dp.callback_query(F.data.startswith("show:"))
async def cb_show_code(c: CallbackQuery):
    code = c.data.split(":")[1]
    row = conn.execute("SELECT title, valid_until, status FROM prizes WHERE code=?", (code,)).fetchone()
    if not row:
        await c.answer("Код не найден", show_alert=True)
        return

    dt = row["valid_until"][:10] if row["valid_until"] else "-"
    await c.answer()
    await c.message.answer(
        f"""🎟 Промокод <code>{code}</code>
Приз: <b>{row['title']}</b>
Статус: {row['status']}
Действует до: {dt}"""
    )

@dp.callback_query(F.data == "terms")
async def cb_terms(c: CallbackQuery):
    await c.answer()
    await c.message.answer(
        "• Приз действует в течение указанного срока.\n"
        "• 1 код = 1 стол. Не суммируется с другими акциями (если не указано иначе).\n"
        "• Предъявите код до закрытия счёта."
    )

# ===== Staff / Admin =====

@dp.message(Command("redeem"))
async def cmd_redeem(message: Message, command: CommandObject):
    if not command.args:
        await message.answer("Использование: /redeem <CODE>")
        return
    code = command.args.strip().upper()
    row = conn.execute("SELECT status, title, valid_until FROM prizes WHERE code=?", (code,)).fetchone()
    if not row:
        await message.answer("❌ Код не найден")
        return
    if row["status"] != "issued":
        await message.answer(f"Статус кода: {row['status']} — погасить нельзя")
        return
    try:
        if datetime.utcnow() > datetime.fromisoformat(row["valid_until"]):
            await message.answer("⏳ Срок действия истёк")
            return
    except Exception:
        pass

    with conn:
        conn.execute(
            "UPDATE prizes SET status='redeemed', redeemed_at=?, redeemed_by=? WHERE code=?",
            (now_iso(), message.from_user.id, code)
        )
    await message.answer(f"✅ Погашено. Приз: <b>{row['title']}</b>")

@dp.message(Command("gifts"))
async def cmd_gifts(message: Message):
    lines = ["🎁 Текущие призы (веса):"]
    lines += [f"- {p['title']}: {p['weight']}%" for p in DEFAULT_PRIZES]
    await message.answer("\n".join(lines))

@dp.message(Command("stats"))
async def cmd_stats(message: Message, command: CommandObject):
    period = (command.args or "today").strip()
    now = datetime.utcnow()
    if period == "today":
        since = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        since = now - timedelta(days=7)
    elif period == "month":
        since = now - timedelta(days=30)
    else:
        await message.answer("Использование: /stats [today|week|month]")
        return

    cnt = conn.execute(
        "SELECT COUNT(*) c FROM feedback WHERE created_at >= ?",
        (since.isoformat(),)
    ).fetchone()["c"]

    if cnt:
        avg = conn.execute(
            "SELECT avg(service), avg(taste), avg(speed), avg(clean) FROM feedback WHERE created_at >= ?",
            (since.isoformat(),)
        ).fetchone()
        await message.answer(
            f"📊 За период: {period}\n"
            f"Отзывов: {cnt}\n"
            f"Средние оценки: сервис {avg[0]:.2f} • вкус {avg[1]:.2f} • скорость {avg[2]:.2f} • чистота {avg[3]:.2f}"
        )
    else:
        await message.answer(f"📊 За период: {period}\nОтзывов пока нет.")

@dp.message(Command("export"))
async def cmd_export(message: Message):
    fname = "export_feedback_prizes.csv"
    path = os.path.abspath(fname)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow([
            "created_at","tg_user_id","visit_id","service","taste","speed","clean","comment",
            "prize_code","prize_title","prize_status","valid_until"
        ])
        rows = conn.execute(
            """
            SELECT f.created_at,f.tg_user_id,f.visit_id,f.service,f.taste,f.speed,f.clean,f.comment,
                   p.code,p.title,p.status,p.valid_until
            FROM feedback f
            LEFT JOIN prizes p ON p.user_id=f.tg_user_id AND p.visit_id=f.visit_id
            ORDER BY f.created_at DESC
            """
        ).fetchall()
        for r in rows:
            w.writerow([
                r["created_at"], r["tg_user_id"], r["visit_id"], r["service"], r["taste"], r["speed"], r["clean"],
                (r["comment"] or "").replace("\n", " "),
                r["code"] if "code" in r.keys() else "",
                r["title"] if "title" in r.keys() else "",
                r["status"] if "status" in r.keys() else "",
                r["valid_until"] if "valid_until" in r.keys() else ""
            ])
    await message.answer_document(FSInputFile(path))

async def main():
    assert BOT_TOKEN and BOT_TOKEN != "8018287894:REPLACE_ME", "Заполните BOT_TOKEN в .env"
    print("Bot started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

