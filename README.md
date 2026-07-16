# airsoft_kitfinder

Сервис подбора страйкбольных «китов»: пользователь находит заранее собранный набор
снаряжения и покупает всё его содержимое (MVP — агрегатор со ссылками на внешние магазины).

## Документация

- [`docs/REQUIREMENTS.md`](docs/REQUIREMENTS.md) — требования
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — архитектура (модель данных, парсеры, API)
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — этапы MVP и статусы

## Стек

- **Бэкенд:** Python 3.12+, FastAPI, PostgreSQL (`backend/`), пакетный менеджер `uv`.
- **Фронтенд:** React + Vite + TypeScript + Mantine (`frontend/`).

## Быстрый старт (dev)

Требуются: `uv`, Node.js, Docker.

```bash
# 1. Поднять PostgreSQL
docker compose up -d db

# 2. Бэкенд (из backend/)
cd backend
cp .env.example .env        # заполнить при необходимости
uv sync
uv run uvicorn app.main:app --reload   # http://localhost:8000/api/docs

# 3. Фронтенд (из frontend/, в отдельном терминале)
cd frontend
npm install
npm run dev                 # http://localhost:5173 (проксирует /api на :8000)
```

## Проверки

```bash
# Бэкенд
cd backend && uv run pytest && uv run ruff check .

# Фронтенд
cd frontend && npm run build
```
