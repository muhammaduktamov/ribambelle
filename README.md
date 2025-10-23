# Ribambelle Feedback Bot (Python, aiogram v3)

Функции:
- Вход по QR `https://t.me/<botname>?start=visit_<VISIT_ID>_<SIGN>` (HMAC-подпись).
- 4 оценки (сервис, вкус, скорость, чистота) + комментарий (по желанию).
- Триггер проблемных отзывов → мгновенное уведомление в менеджерский чат с кнопкой «Принято».
- Рандомайзер призов (веса) → промокод на следующее посещение с ограничением по сроку.
- Команда `/redeem <CODE>` для погашения (официант/касса).
- Команды админа: `/stats`, `/gifts`, `/gifts_set JSON`, `/export`.

## Быстрый старт
1) Python 3.10+
2) Создать `.env` из примера:
```
cp .env.example .env
# отредактируйте BOT_TOKEN, SECRET_KEY, MANAGERS_CHAT_ID
```
3) Установка:
```
pip install -r requirements.txt
```
4) Запуск:
```
python app.py
```

## QR-ссылка
Формат: `https://t.me/<botname>?start=visit_<VISIT_ID>_<SIGN>`  
Где `SIGN = hex(hmac_sha256(SECRET_KEY, VISIT_ID))`  
Пример генерации подписи: `python tools/sign_visit.py VISIT_ABC`

## Таблицы
SQLite `bot.db` (создаётся автоматически):
- guests(tg_user_id, username, phone, created_at)
- visits(visit_id, tg_user_id, created_at)
- feedback(id, tg_user_id, visit_id, service, taste, speed, clean, comment, photo_id, created_at, alert_sent)
- prizes(code, title, type, valid_until, user_id, visit_id, status, created_at, redeemed_at, redeemed_by)

## Импорт/экспорт
- `/export` отправит CSV с данными отзывов и призов.
