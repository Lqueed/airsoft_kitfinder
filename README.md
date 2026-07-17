# airsoft_kitfinder

Сервис подбора страйкбольных «китов»: пользователь находит заранее собранный набор
снаряжения и покупает всё его содержимое (MVP — агрегатор со ссылками на внешние магазины).

## Документация

- [`docs/REQUIREMENTS.md`](docs/REQUIREMENTS.md) — требования
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — архитектура (модель данных, парсеры, API)
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — этапы MVP и статусы
- [`docs/SHOPS.md`](docs/SHOPS.md) — реестр магазинов для парсинга и их статус

## Стек

- **Бэкенд:** Python 3.12+, FastAPI, PostgreSQL (`backend/`), пакетный менеджер `uv`.
- **Фронтенд:** React + Vite + TypeScript + Mantine (`frontend/`).

## Возможности (готово, M0–M6)

Публичная витрина:
- `/` — каталог китов (фильтры роль/привод/бюджет в URL) + строка поиска;
- `/kits/:slug` — деталка кита (выбор вариантов, «Итого», ссылки «Купить в магазине»);
- `/wizard` — подбор кита по опыту/роли/бюджету;
- `/search?q=` — поиск по названию и товарам состава (с опечатками, `pg_trgm`).

Админка (`/admin`, вход по паролю):
- список и редактор китов (позиции fixed/flexible, курация вариантов, публикация);
- каталог магазинов: поиск по сырым офферам и ручная привязка к товарам.

Данные наполняются парсерами шести магазинов (`app.cli parse`) и матчингом
(`app.cli rematch`): strikeplanet, zorg, mangoost, airgun, pnevmat24 (static) и
airsoftstore (через Playwright, JS-челлендж); см. [`docs/SHOPS.md`](docs/SHOPS.md).
Остаётся по роадмапу: airsoft-rus (Cloudflare, отложен) и **продакшенизация**
(деплой, cron, бэкапы).

## Быстрый старт (dev)

Требуются: `uv`, Node.js, Docker.

```bash
# 1. Поднять PostgreSQL
docker compose up -d db

# 2. Бэкенд (из backend/)
cd backend
cp .env.example .env        # заполнить при необходимости
uv sync
uv run playwright install chromium     # браузер для парсера airsoftstore (JS-челлендж)
uv run alembic upgrade head            # создать схему БД
uv run python -m app.cli seed          # заполнить справочник категорий
uv run uvicorn app.main:app --reload   # http://localhost:8000/api/docs

# 3. Фронтенд (из frontend/, в отдельном терминале)
cd frontend
npm install
npm run dev                 # http://localhost:5173 (проксирует /api на :8000)
```

## Полезные команды

```bash
# Сгенерировать bcrypt-хеш пароля админа для ADMIN_PASSWORD_HASH в .env
uv run python -m app.cli hash-password "твой-пароль"
```

## Проверки

```bash
# Бэкенд
cd backend && uv run pytest && uv run ruff check .

# Фронтенд
cd frontend && npm run build
```
