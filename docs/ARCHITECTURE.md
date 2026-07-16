# airsoft_kitfinder — архитектура

Утверждена 2026-07-16. Требования — в [REQUIREMENTS.md](REQUIREMENTS.md),
план работ — в [ROADMAP.md](ROADMAP.md).

## Общая картина

Монолит: FastAPI (`backend/`) + SPA React/Vite/TS (`frontend/`) + PostgreSQL
(docker-compose). Парсеры — часть того же Python-пакета, запускаются отдельной
CLI-командой по cron, **не** внутри веб-процесса.

```
Пользователь ──► SPA (React) ──► FastAPI /api/* ──► PostgreSQL
Админ ────────► SPA /admin/* ──► FastAPI /api/admin/* (cookie-сессия)
cron ─────────► uv run python -m app.cli parse ──► парсеры-плагины ──► PostgreSQL
```

## Модель данных (PostgreSQL, SQLAlchemy 2.x typed + Alembic)

| Таблица | Назначение | Ключевые поля |
|---|---|---|
| `shops` | Магазины-источники | `code` (unique, = код парсера-плагина), `name`, `base_url`, `is_active` |
| `categories` | **Наша** таксономия (не категории магазинов) | `slug`, `name`, `parent_id` (дерево глубины 1) |
| `products` | Каноническая сущность товара (одна на модель, независимо от магазина) | `name`, `slug`, `category_id`, `brand`, `match_key` (нормализованное имя, indexed), `attrs` JSONB (GIN) |
| `offers` | Предложение конкретного магазина | `shop_id` + `external_id` (**unique — ключ идемпотентности**), `product_id` nullable (null = несматчен), `url`, `raw_title`, `raw_category`, `price`, `in_stock`, `is_active`, `first_seen_at`, `last_seen_at` |
| `price_history` | История цен | `offer_id`, `price`, `in_stock`, `recorded_at`; запись **только при изменении** |
| `kits` | Киты | `slug`, `name`, `description`, `role`, `drive_type`, `experience_level`, `status` (`draft\|published`); бюджетная вилка **не денормализуется** — считается из offers |
| `kit_items` | Позиции кита, оба типа в одной таблице | `item_type` (`fixed\|flexible`) + CHECK; fixed → `product_id`; flexible → `category_id`, `max_price`, `attr_filters` JSONB; `title`, `is_required`, `sort_order` |
| `kit_item_candidates` | Ручная курация вариантов flexible-позиции | `kit_item_id`, `product_id`, `is_pinned`, `is_excluded` |

Enum'ы (`role`, `drive_type`, `experience_level`, `status`, `item_type`) — Python-enum +
CHECK-констрейнт, без справочных таблиц.

Варианты flexible-позиции = (товары по критериям ∪ pinned) − excluded.

## Матчинг товаров между магазинами (без ML)

Проблема: один товар в трёх магазинах называется тремя способами.

1. **Авто-матч по `match_key`**: нормализация `raw_title` — lowercase, удаление
   пунктуации и стоп-слов («привод», «страйкбольный»), словарик транслит-вариантов
   брендов, сортировка токенов. Совпадение → привязка к существующему product;
   нет → **авто-создание** product (категория — по маппингу `raw_category` → наша,
   словарик на магазин).
2. **Ручной разбор в админке**: экран несматченных/дублей, перепривязка оффера
   (`POST /api/admin/offers/{id}/link`). Полноценный merge дублей — за MVP.

Принцип: парсеры **никогда не пишут в `products` напрямую** — только через
`app/services/matching.py`. Вся нормализация живёт в одном месте.

## Парсеры

- Контракт `app/parsers/base.py`: `ShopParser` (ABC; `code/name/base_url`;
  `iter_offers() -> AsyncIterator[ParsedOffer]`), DTO `ParsedOffer`
  (`external_id, url, title, price, in_stock, raw_category, image_url`).
- Один файл на магазин: `app/parsers/shops/<code>.py`. Реестр — **явный dict**
  в `app/parsers/registry.py`. Добавить магазин = файл + строка в реестре
  (запись в `shops` — авто-upsert по `code`).
- HTTP: `httpx.AsyncClient`, таймауты, ретраи, rate limit 1–2 rps, вежливый
  User-Agent. HTML — `selectolax`. CSS-селекторы — константами в шапке класса.
- **Запуск:** `uv run python -m app.cli parse [--shop <code>]` + cron (ночью раз
  в сутки). Не APScheduler в веб-процессе: долгие прогоны, независимый рестарт,
  простая отладка.

### Ingest-конвейер (`app/services/ingest.py`)

1. Фиксируем `run_started_at`.
2. По каждому `ParsedOffer`: upsert в `offers` по `(shop_id, external_id)`,
   обновление `last_seen_at`; при изменении цены/наличия — строка в
   `price_history`; новый оффер — через матчинг.
3. После прогона: деактивация офферов с `last_seen_at < run_started_at`
   (не удаляем — история и «воскрешение»).
4. **Страховочный порог**: если распарсено аномально мало (< N% привычного объёма
   или 0 карточек) — прогон FAILED, деактивация **не выполняется** (смена вёрстки
   не должна «убить» офферы магазина).
5. try/except вокруг каждой карточки; итоговая сводка в лог
   (всего/новых/изменённых/деактивированных/ошибок).

Тесты парсеров — на сохранённых HTML-фикстурах (`tests/fixtures/<shop>/*.html`),
без сети.

## API

### Публичные (`/api`)

| Метод | Путь | Назначение |
|---|---|---|
| GET | `/api/kits` | Каталог: `?role=&drive_type=&budget_min=&budget_max=&q=&page=`; у кита `price_min`/`price_max` |
| GET | `/api/kits/{slug}` | Деталка: позиции; fixed → офферы по магазинам; flexible → варианты; вилка цены |
| POST | `/api/wizard/recommend` | `{experience, role, budget}` → ранжированные киты (прозрачный скоринг, без ML) |
| GET | `/api/search?q=` | Поиск китов: `ILIKE` + `pg_trgm` (опечатки) |
| GET | `/api/meta` | Справочники: роли, типы приводов, категории |

### Админские (`/api/admin`, за `Depends(require_admin)`)

| Метод | Путь | Назначение |
|---|---|---|
| POST | `/login`, `/logout`; GET `/me` | Cookie-сессия |
| GET/POST/PATCH/DELETE | `/kits`, `/kits/{id}` | CRUD китов (включая черновики) |
| POST | `/kits/{id}/publish`, `/unpublish` | Публикация |
| POST/PATCH/DELETE | `/kits/{id}/items`, `/items/{id}` | Позиции обоих типов |
| GET | `/products?q=&category_id=` | Автокомплит товаров для привязки |
| GET | `/offers?unmatched=true` | Несматченные офферы |
| POST | `/offers/{id}/link` | Привязка оффера к product |
| GET | `/kit-items/{id}/preview` | Предпросмотр вариантов flexible-позиции |

Расчёт цены кита — один сервис `app/services/kit_pricing.py` (мин = сумма минимальных
активных офферов обязательных позиций; для flexible — самый дешёвый подходящий вариант).
Используется каталогом, деталкой и визардом.

## Фронтенд

- **Библиотеки:** react-router, TanStack Query (весь серверный стейт; отдельный
  стейт-менеджер не нужен), **Mantine** (UI-кит: формы, таблицы, модалки, Stepper),
  `fetch` + тонкая обёртка `src/api/client.ts`.
- **Страницы:** `/` каталог (фильтры в query-параметрах URL); `/kits/:slug` деталка
  (выбор вариантов flexible, липкая панель «Итого: от X до Y ₽»); `/wizard`
  (Mantine Stepper, 3 шага); `/admin/*` — логин, таблица китов, редактор кита
  (fixed через автокомплит, flexible через форму критериев + предпросмотр),
  несматченные офферы. Гард — `GET /api/admin/me`, 401 → редирект на логин.
- Dev: Vite `server.proxy` `/api` → `localhost:8000`.
- Ссылки «Купить»: `target="_blank" rel="noopener nofollow"`.

## Аутентификация админа

Один пароль, без таблицы пользователей:

- `.env`: `ADMIN_PASSWORD_HASH` (bcrypt) + `SECRET_KEY`.
- `POST /api/admin/login {password}` → bcrypt-проверка → подписанная httpOnly
  SameSite=Lax Secure cookie (`itsdangerous.TimestampSigner`, TTL ~14 дней).
- Пауза 1–2 с при неверном пароле (анти-брутфорс уровня личного проекта).
- Расширение до пользователей: добавится таблица `users`, cookie-механика та же.

## Ключевые принципы

1. **Оффер — единица покупки**: будущая корзина ссылается на `offer_id`,
   текущая схема не переделывается.
2. **Вся нормализация — в matching.py**; парсеры тупые: скачал → распарсил → DTO.
3. **Цены не денормализуются**: источник правды — `offers`, расчёт в `kit_pricing.py`.
4. **Парсер не может молча уничтожить данные**: деактивация только при успешном
   прогоне выше порога.

## Структура backend

```
backend/
  app/
    main.py  config.py  db.py  auth.py  cli.py
    models/        # SQLAlchemy-модели (catalog.py)
    schemas/       # Pydantic-схемы API
    api/           # публичные роутеры
    api/admin/     # админские роутеры
    services/      # ingest.py, matching.py, kit_pricing.py
    parsers/       # base.py, registry.py, shops/<code>.py
  alembic/
  tests/           # + fixtures/<shop>/*.html
  pyproject.toml
```
