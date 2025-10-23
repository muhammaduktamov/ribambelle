import os, asyncio, logging, sqlite3, random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.filters import Command, CommandStart
from aiogram.client.default import DefaultBotProperties
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMINS = [int(x) for x in os.getenv("ADMINS","").split(",") if x.strip().isdigit()]
TIMEZONE = os.getenv("TIMEZONE","Asia/Tashkent")
SURVEY_HOUR = int(os.getenv("SURVEY_HOUR","10"))
DISCOUNT_PERCENT = int(os.getenv("DISCOUNT_PERCENT","10"))
COUPON_EXPIRES_DAYS = int(os.getenv("COUPON_EXPIRES_DAYS","30"))
SURVEY_MODE = os.getenv("SURVEY_MODE", "immediate")  # immediate | scheduled

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

# aiogram 3.7+: parse_mode через DefaultBotProperties
bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
tz = ZoneInfo(TIMEZONE)
scheduler = AsyncIOScheduler(timezone=tz)

DB = "data.db"

def db():
    return sqlite3.connect(DB)

def setup_db():
    with db() as conn:
        c = conn.cursor()
        c.execute("""
        CREATE TABLE IF NOT EXISTS users(
            chat_id INTEGER PRIMARY KEY,
            first_name TEXT,
            username TEXT,
            consent INTEGER DEFAULT 1,
            expect_bill INTEGER DEFAULT 0,
            created_at TEXT
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS visits(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            bill_id TEXT,
            visited_at TEXT,
            survey_sent INTEGER DEFAULT 0
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS surveys(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            bill_id TEXT,
            food INTEGER,
            service INTEGER,
            clean INTEGER,
            nps INTEGER,
            comment TEXT,
            created_at TEXT
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS coupons(
            code TEXT PRIMARY KEY,
            chat_id INTEGER,
            bill_id TEXT,
            discount INTEGER,
            expires_at TEXT,
            used INTEGER DEFAULT 0,
            used_at TEXT
        )""")
        conn.commit()

def gen_code(n=8):
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(random.choice(alphabet) for _ in range(n))

def main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📝 Оценить визит"),
                   KeyboardButton(text="🎟 Мой купон")]],
        resize_keyboard=True
    )

def survey_keyboard(step: str):
    if step == "food":
        label = "🍽 Оцените кухню (1–5)"
    elif step == "service":
        label = "🤵 Оцените обслуживание (1–5)"
    elif step == "clean":
        label = "🧼 Оцените чистоту/атмосферу (1–5)"
    elif step == "nps":
        label = "⭐️ Порекомендуете нас друзьям? (0–10)"
    else:
        label = ""
    if step == "nps":
        rows = [
            [InlineKeyboardButton(text=str(x), callback_data=f"nps:{x}") for x in range(0,6)],
            [InlineKeyboardButton(text=str(x), callback_data=f"nps:{x}") for x in range(6,11)],
        ]
    else:
        rows = [[InlineKeyboardButton(text=str(x), callback_data=f"{step}:{x}") for x in range(1,6)]]
    return label, InlineKeyboardMarkup(inline_keyboard=rows)

async def notify_admins(text: str):
    for admin_id in ADMINS:
        try:
            await bot.send_message(admin_id, text)
        except Exception:
            pass

async def send_coupon(chat_id: int, bill_id: str | None):
    code = gen_code()
    expires_at = (datetime.now(tz) + timedelta(days=COUPON_EXPIRES_DAYS)).strftime("%Y-%m-%d")
    with db() as conn:
        conn.execute(
            "INSERT INTO coupons(code, chat_id, bill_id, discount, expires_at) VALUES (?,?,?,?,?)",
            (code, chat_id, bill_id or "-", DISCOUNT_PERCENT, expires_at),
        )
        conn.commit()
    text = (
        f"🎉 Спасибо за отзыв!\n"
        f"Ваш персональный купон: <b>{code}</b>\n"
        f"Скидка: <b>{DISCOUNT_PERCENT}%</b>\n"
        f"Действует до: <b>{expires_at}</b>\n"
        f"Покажите этот код при следующем визите."
    )
    await bot.send_message(chat_id, text)

async def start_survey(chat_id: int, bill_id: str):
    label, kb = survey_keyboard("food")
    with db() as conn:
        conn.execute(
            "INSERT INTO surveys(chat_id, bill_id, created_at) VALUES (?,?,?)",
            (chat_id, bill_id, datetime.now(tz).isoformat()),
        )
        conn.commit()
    await bot.send_message(chat_id, f"🙏 Спасибо за визит в <b>Рибамбель</b>!\n{label}", reply_markup=kb)

# ──────────────────────── HANDLERS ─────────────────────────

@dp.message(CommandStart())
async def cmd_start(m: Message):
    setup_db()
    with db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users(chat_id, first_name, username, consent, created_at) VALUES (?,?,?,?,?)",
            (m.chat.id, m.from_user.first_name, m.from_user.username, 1, datetime.now(tz).isoformat()),
        )
        conn.commit()
    await m.answer(
        "👋 Добро пожаловать в <b>Рибамбель</b>!\n"
        "Оцените визит и получите персональный купон на скидку 🎁\n\n"
        "Нажмите «📝 Оценить визит» и отправьте номер счёта.",
        reply_markup=main_kb()
    )

@dp.message(F.text == "📝 Оценить визит")
async def ask_bill(m: Message):
    with db() as conn:
        conn.execute("UPDATE users SET expect_bill=1 WHERE chat_id=?", (m.chat.id,))
        conn.commit()
    await m.answer("Пожалуйста, отправьте <b>номер счёта</b> (например: 123456).")

@dp.message(F.text == "🎟 Мой купон")
@dp.message(Command("coupon"))
async def my_coupon(m: Message):
    with db() as conn:
        row = conn.execute(
            "SELECT code, discount, expires_at, used FROM coupons WHERE chat_id=? ORDER BY rowid DESC LIMIT 1",
            (m.chat.id,)
        ).fetchone()
    if not row:
        await m.answer("У вас пока нет купонов. Получите его после заполнения короткой анкеты 🙌")
        return
    code, discount, expires_at, used = row
    status = "использован ✅" if used else "активен"
    await m.answer(f"🎟 Ваш купон: <b>{code}</b>\nСкидка: <b>{discount}%</b>\nДействует до: <b>{expires_at}</b>\nСтатус: {status}")

@dp.message(Command("visit"))
async def cmd_visit(m: Message):
    args = m.text.split(maxsplit=1)
    if len(args) < 2:
        await m.answer("Укажите номер счёта: /visit 123456")
        return
    bill_id = args[1].strip()
    with db() as conn:
        conn.execute(
            "INSERT INTO visits(chat_id, bill_id, visited_at) VALUES (?,?,?)",
            (m.chat.id, bill_id, datetime.now(tz).isoformat()),
        )
        conn.execute("UPDATE users SET expect_bill=0 WHERE chat_id=?", (m.chat.id,))
        conn.commit()

    if SURVEY_MODE == "immediate":
        await m.answer(
            f"✅ Визит по счёту <b>#{bill_id}</b> зарегистрирован.\n"
            f"Начинаем опрос — это займёт 30–40 секунд ✨"
        )
        await start_survey(m.chat.id, bill_id)
    else:
        await m.answer(
            f"✅ Визит по счёту <b>#{bill_id}</b> зарегистрирован.\n"
            f"Анкета придёт завтра в {SURVEY_HOUR:02d}:00. Спасибо!",
            reply_markup=main_kb()
        )

@dp.message(F.text & ~F.text.startswith(("/",)))
async def capture_bill_or_comment(m: Message):
    # если ждём номер счёта — считаем текст номером
    with db() as conn:
        row = conn.execute("SELECT expect_bill FROM users WHERE chat_id=?", (m.chat.id,)).fetchone()
        expect_bill = row and row[0] == 1
    if expect_bill:
        bill_id = "".join(ch for ch in m.text if ch.isalnum())
        if not bill_id:
            await m.answer("Пожалуйста, пришлите номер счёта цифрами, например: 123456")
            return
        with db() as conn:
            conn.execute(
                "INSERT INTO visits(chat_id, bill_id, visited_at) VALUES (?,?,?)",
                (m.chat.id, bill_id, datetime.now(tz).isoformat()),
            )
            conn.execute("UPDATE users SET expect_bill=0 WHERE chat_id=?", (m.chat.id,))
            conn.commit()

        if SURVEY_MODE == "immediate":
            await m.answer(
                f"✅ Визит по счёту <b>#{bill_id}</b> зарегистрирован.\n"
                f"Начинаем опрос — это займёт 30–40 секунд ✨"
            )
            await start_survey(m.chat.id, bill_id)
        else:
            await m.answer(
                f"✅ Визит по счёту <b>#{bill_id}</b> зарегистрирован.\n"
                f"Анкета придёт завтра в {SURVEY_HOUR:02d}:00. Спасибо!",
                reply_markup=main_kb()
            )
        return

    # иначе — это комментарий к последней анкете
    text = m.text.strip()
    with db() as conn:
        r = conn.execute(
            "SELECT id, bill_id, food, service, clean, nps FROM surveys WHERE chat_id=? ORDER BY id DESC LIMIT 1",
            (m.chat.id,)
        ).fetchone()
        if not r:
            return
        sid, bill_id, food, service, clean, nps = r
        conn.execute("UPDATE surveys SET comment=? WHERE id=?", (text, sid))
        conn.commit()
    await m.reply("Получили ваш комментарий ❤️")
    await send_coupon(m.chat.id, bill_id)

    # эскалация при плохой оценке
    if ADMINS:
        bad = (
            (food is not None and food < 4) or
            (service is not None and service < 4) or
            (clean is not None and clean < 4) or
            (nps is not None and nps <= 6)
        )
        if bad:
            await notify_admins(
                "🚨 <b>Негативный отзыв</b>\n"
                f"Гость: <code>{m.chat.id}</code>\n"
                f"Счёт: <code>{bill_id or '-'}</code>\n"
                f"🍽 Кухня: {food or '-'} | 🤵 Сервис: {service or '-'} | 🧼 Чистота: {clean or '-'} | ⭐️ NPS: {nps or '-'}\n"
                f"💬 Комментарий: {text}\n"
                "→ Свяжитесь с гостем оперативно."
            )

@dp.message(Command("redeem"))
async def cmd_redeem(m: Message):
    args = m.text.split(maxsplit=1)
    if len(args) < 2:
        await m.answer("Укажите код купона: /redeem ABCD1234")
        return
    code = args[1].strip().upper()
    with db() as conn:
        row = conn.execute("SELECT code, discount, expires_at, used FROM coupons WHERE code=?", (code,)).fetchone()
        if not row:
            await m.answer("Купон не найден.")
            return
        code, discount, expires_at, used = row
        if used:
            await m.answer("Купон уже использован.")
            return
        if expires_at < datetime.now(tz).strftime("%Y-%m-%d"):
            await m.answer("Срок действия купона истёк.")
            return
        conn.execute("UPDATE coupons SET used=1, used_at=? WHERE code=?", (datetime.now(tz).isoformat(), code))
        conn.commit()
    await m.answer(f"✅ Купон <b>{code}</b> применён. Скидка {discount}% предоставлена.")

@dp.message(Command("stats"))
async def cmd_stats(m: Message):
    if m.chat.id not in ADMINS:
        return
    with db() as conn:
        u = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        v = conn.execute("SELECT COUNT(*) FROM visits").fetchone()[0]
        s = conn.execute("SELECT COUNT(*) FROM surveys").fetchone()[0]
        c = conn.execute("SELECT COUNT(*) FROM coupons WHERE used=1").fetchone()[0]
    await m.answer(
        f"👥 Пользователи: {u}\n"
        f"🧾 Визиты: {v}\n"
        f"📝 Анкеты: {s}\n"
        f"🎟 Купонов использовано: {c}"
    )

def next_step(current: str):
    order = ["food", "service", "clean", "nps"]
    i = order.index(current)
    return order[i+1] if i < len(order)-1 else None

@dp.callback_query(F.data.startswith(("food:","service:","clean:","nps:")))
async def on_rate(cq: CallbackQuery):
    step, val = cq.data.split(":")
    val = int(val)
    chat_id = cq.message.chat.id
    with db() as conn:
        r = conn.execute(
            "SELECT id, bill_id FROM surveys WHERE chat_id=? ORDER BY id DESC LIMIT 1",
            (chat_id,)
        ).fetchone()
        if not r:
            conn.execute(
                "INSERT INTO surveys(chat_id, bill_id, created_at) VALUES (?,?,?)",
                (chat_id, None, datetime.now(tz).isoformat())
            )
            conn.commit()
            r = conn.execute(
                "SELECT id, bill_id FROM surveys WHERE chat_id=? ORDER BY id DESC LIMIT 1",
                (chat_id,)
            ).fetchone()
        sid, bill_id = r
        field = {"food":"food","service":"service","clean":"clean","nps":"nps"}[step]
        conn.execute(f"UPDATE surveys SET {field}=? WHERE id=?", (val, sid))
        conn.commit()
    ns = next_step(step)
    if ns:
        label, kb = survey_keyboard(ns)
        await cq.message.answer(label, reply_markup=kb)
    else:
        await cq.message.answer("Спасибо! Напишите короткий комментарий (или «-», чтобы пропустить).")
    await cq.answer()

# ─────────────── SCHEDULER ───────────────

async def survey_scheduler():
    now = datetime.now(tz)
    with db() as conn:
        rows = conn.execute(
            "SELECT id, chat_id, bill_id, visited_at, survey_sent FROM visits WHERE survey_sent=0"
        ).fetchall()
        for vid, chat_id, bill_id, visited_at, sent in rows:
            try:
                visited_dt = datetime.fromisoformat(visited_at)
            except Exception:
                visited_dt = now
            due = (visited_dt + timedelta(days=1)).replace(
                hour=SURVEY_HOUR, minute=0, second=0, microsecond=0
            )
            if now >= due and (now - due) <= timedelta(hours=1):
                try:
                    await start_survey(chat_id, bill_id)
                    conn.execute("UPDATE visits SET survey_sent=1 WHERE id=?", (vid,))
                    conn.commit()
                except Exception as e:
                    logging.exception("Failed to send survey: %s", e)

async def on_startup():
    setup_db()
    if SURVEY_MODE == "scheduled":
        scheduler.add_job(survey_scheduler, "interval", minutes=5, id="survey-tick")
        scheduler.start()
        logging.info("Scheduler started (scheduled mode).")
    else:
        logging.info("Immediate survey mode enabled.")

async def main():
    await on_startup()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

