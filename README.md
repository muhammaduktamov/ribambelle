# Ribambelle Feedback Bot (Render-ready)

Telegram-бот для пост-визитной оценки и скидочных купонов. Готов к деплою на Render как **Background Worker**.

## Локальный запуск (Mac)
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# отредактируй .env и затем:
export $(cat .env | xargs)
python app.py
```

## Деплой на Render (Blueprint)
1) Запушь этот код в GitHub (репозиторий).
2) На render.com → **New** → **Blueprint** → выбери репозиторий.
3) Render прочитает `render.yaml` и создаст Worker.
4) В Variables добавь `BOT_TOKEN` (секрет), остальное можно оставить как в yaml.
5) Запусти деплой.

> Сейчас используется SQLite (файл data.db). На бесплатном Render диск может обнуляться при ребилде. Для продакшена стоит перейти на PostgreSQL или платный Persistent Disk.

## Команды бота
- `/start` — регистрация/согласие.
- `/visit <bill_id>` — зафиксировать визит (опрос придет на след. день в SURVEY_HOUR).
- `/redeem <COUPON>` — погасить купон.
- `/stats` — краткая статистика (только для ADMINS).

## Импорт визитов
CSV с колонками: `chat_id,bill_id,visited_at(ISO)` → см. `import_visits.py`.
