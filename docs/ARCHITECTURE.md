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
| `kit_images` | Загруженные фото кита (файлы в S3) | `kit_id` (FK cascade), `object_key` (ключ в бакете), `sort_order`; до 10 на кит |

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

**Категорийные ключи.** Для категорий, где сортировка токенов раскалывает один
товар (разный формат, язык, артикулы), используется структурный `match_key`.
Реализовано для шаров (`bbs`): ключ `bbs:brand|weight|color|tracer` (бренд с
алиасами, вес `0.NN`, цвет с дефолтом «белый», флаг трассера); распознанные
атрибуты пишутся в `products.attrs`. Нераспознанное/прочие категории — общий
токен-нормализатор (фолбэк).

## Парсеры

- Контракт `app/parsers/base.py`: `ShopParser` (ABC; `code/name/base_url`;
  `iter_offers() -> AsyncIterator[ParsedOffer]`), DTO `ParsedOffer`
  (`external_id, url, title, price, in_stock, raw_category, image_url`).
- Один файл на магазин: `app/parsers/shops/<code>.py`. Реестр — **явный dict**
  в `app/parsers/registry.py`. Добавить магазин = файл + строка в реестре
  (запись в `shops` — авто-upsert по `code`).
- HTTP: `httpx.AsyncClient`, таймауты, ретраи, rate limit 1–2 rps, вежливый
  User-Agent. HTML — `selectolax`. CSS-селекторы — константами в шапке класса.
- **Playwright — только для магазинов с JS-анти-ботом** (первый такой —
  `airsoftstore`, VirtueMart с JS-челленджем). Остальные каталоги рендерятся
  server-side, и для них `httpx + selectolax` легче/быстрее/надёжнее для крона.
  Playwright-парсер устроен так, что браузер нужен **только для добычи HTML**:
  `parse_listing` остаётся чистой функцией (тест на фикстуре, без браузера), а
  `iter_offers` лениво импортирует `playwright.async_api`, поднимает headless
  chromium, проходит челлендж и берёт `page.content()`. Реестр и ingest-конвейер
  не меняются. Зависимость `playwright` + разовая установка браузера
  `uv run playwright install chromium`.
- **Cloudflare managed challenge (airsoft-rus.ru) обычным Playwright не пробивается** —
  см. [SHOPS.md](SHOPS.md); отложено.
- **Реализованные парсеры (6):** `strikeplanet`, `zorg`, `mangoost`, `airgun`,
  `pnevmat24` (static, httpx + selectolax) и `airsoftstore` (Playwright, JS-челлендж).
  Профильные страйкбол-магазины парсятся целиком; пневмо-/оружейные (`airgun`,
  `pnevmat24`) — только страйкбол + снаряжение (одежда, обувь, бронежилеты/плитники,
  подсумки) по белому списку категорий, оружие/пневматика в обход не берутся.
  `raw_category` сохраняется — финальная фильтрация возможна на слое матчинга.
  Детали площадок, категорий и селекторов — в [SHOPS.md](SHOPS.md).
- **strikeplanet.ru** (1C-Bitrix). Парсер обходит дерево каталога от корня (BFS/DFS
  с дедупом URL), пагинация через `?PAGEN_1=`. `external_id` = Bitrix
  `data-element-id`, наличие — по кнопке «в корзину» (`.cart--add`; её отсутствие +
  «Сообщить о поступлении» = нет в наличии). `ingest_shop(..., limit=N)` —
  smoke-прогон/защитный кап (деактивацию пропускает).
- **Способы обхода различаются по площадке:** пагинация `?PAGEN_1=` (Bitrix:
  strikeplanet, zorg), вся категория одной страницей (`/all/` у mangoost,
  `?limit=<много>` у airgun), постранично `?page=N` (pnevmat24 / OpenCart).
  Внутри магазина — дедуп офферов по `external_id` (родительские категории
  агрегируют поддерево).
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
| GET | `/api/kits` | Каталог: `?role=&drive_type=&budget_min=&budget_max=&page=` (только published, бюджет = пересечение вилок); у кита `price_min`/`price_max`/`complete` |
| GET | `/api/kits/{slug}` | Деталка: позиции; fixed → офферы по магазинам; flexible → варианты с офферами; вилка цены |
| POST | `/api/wizard/recommend` | `{experience, role, budget}` → ранжированные киты (роль/уровень — бонус, бюджет — близость; без ML) |
| GET | `/api/search?q=` | Поиск китов по названию/описанию и товарам состава: `pg_trgm` `word_similarity` (опечатки) |
| GET | `/api/meta` | Справочники: роли, типы приводов, уровни, категории, магазины |

### Админские (`/api/admin`, за `Depends(require_admin)`)

| Метод | Путь | Назначение |
|---|---|---|
| POST | `/login`, `/logout`; GET `/me` | Cookie-сессия |
| GET/POST/PATCH/DELETE | `/kits`, `/kits/{id}` | CRUD китов (включая черновики) |
| POST | `/kits/{id}/publish`, `/unpublish` | Публикация |
| POST/PATCH/DELETE | `/kits/{id}/items`, `/items/{id}` | Позиции обоих типов |
| POST | `/kits/{id}/images` | Загрузка фото кита (multipart, до 10; первое → обложка) |
| POST/DELETE | `/kit-images/{id}/cover`, `/kit-images/{id}` | Сделать обложкой / удалить фото (переназначает обложку) |
| GET | `/product-search?q=&category_id=` | Автокомплит товаров для привязки (fixed-позиции, merge, ручной матчинг) |
| GET | `/products?q=&category_id=&no_category=&multishop=&sort=&order=&page=&page_size=` | Список товаров с агрегатами (число офферов/магазинов, вилка цены), поиск/фильтры/сортировка/пагинация |
| GET/PATCH/DELETE | `/products/{id}` | Карточка товара + офферы; правка полей (`match_key`/`slug` неизменны); удаление (409, если товар в fixed-ките; офферы отвязываются, курация чистится) |
| POST | `/products/{target}/merge` | Слияние дублей: source-товары вливаются в цель (офферы/позиции/курация перевешиваются, дубли удаляются) |
| POST | `/products/bulk` | Массовые операции (`set_category`/`set_brand`/`delete`) с per-item результатом (savepoint на элемент) |
| GET | `/offers?shop=&q=&status=&active=` | Каталог магазина: поиск по сырым офферам (`status`=all/unmatched/matched), `pg_trgm` по `raw_title` |
| POST | `/offers/{id}/link`, `/offers/{id}/unlink` | Привязка/отвязка оффера к product |
| POST | `/offers/{id}/create-product` | Создать товар из оффера (find-or-create через matching.py) |
| GET | `/kit-items/{id}/preview` | Предпросмотр вариантов flexible-позиции |
| GET/PUT | `/kit-items/{id}/candidates` | Курация flexible-позиции: закрепить/исключить товар (сброс флагов удаляет) |

Расчёт цены кита — один сервис `app/services/kit_pricing.py`: `price_min` = сумма
минимальных активных офферов по **обязательным** позициям (для flexible — самый
дешёвый подходящий вариант); `price_max` = по обязательным (самый дорогой вариант)
плюс опциональные позиции. Неполный кит (обязательная позиция без цены) → `complete=false`.
Используется каталогом, деталкой и визардом.

**Поисковые индексы** (`pg_trgm`, GIN): `offers.raw_title` (каталог магазина),
`products.name` и `kits.name` (публичный поиск); GIN по `products.attrs` (фильтр flexible).

**Управление товарами (`app/api/admin/products.py`).** Чистка результатов матчинга:
объединение дублей (merge), правка полей, привязка/отвязка офферов, создание товара
из оффера, массовые операции. Ключевые инварианты:
- `match_key`/`slug` при ручной правке **не меняются** — это ключ дедупликации офферов;
  ручное имя/бренд/категория не должны рассыпать матчинг. Создание товара из оффера
  идёт только через `matching.create_product_from_offer` (find-or-create по `match_key`).
- На `products.id` ссылаются 3 FK без `ondelete` (`offers`, `kit_items`,
  `kit_item_candidates`), поэтому merge/delete транзакционно разбирают ссылки:
  офферы и fixed-позиции перевешиваются массово, курация (`kit_item_candidates`
  с UNIQUE `(kit_item_id, product_id)`) сводится в Python с OR-фолдингом флагов.
  Удаление товара, который является целью **fixed**-позиции кита, запрещено (409).
  Для чистки дублей предпочтителен merge (delete + повторный `rematch` «воскресит»
  товар по тому же `match_key`).
- Агрегаты списка (число офферов/магазинов, вилка цены) — один сгруппированный
  подзапрос по `offers` с `FILTER`, без N+1 на ~22 тыс товаров.

## Фронтенд

- **Библиотеки:** react-router, TanStack Query (весь серверный стейт; отдельный
  стейт-менеджер не нужен), **Mantine** (UI-кит: формы, таблицы, модалки, Stepper),
  `fetch` + тонкая обёртка `src/api/client.ts`.
- **Страницы:** `/` каталог (фильтры в query-параметрах URL); `/kits/:slug` деталка
  (выбор вариантов flexible, липкая панель «Итого: от X до Y ₽»); `/wizard`
  (Mantine Stepper, 3 шага); `/admin/*` — логин, таблица китов, редактор кита
  (fixed через автокомплит, flexible через форму критериев + предпросмотр),
  **страница «Товары»** (`/admin/products`: список с агрегатами, поиск/фильтры/сортировка,
  чекбоксы + массовые действия, модалка карточки с правкой полей, офферами и ручным
  матчингом/merge), каталог магазинов (офферы + привязка/создание товара). Гард —
  `GET /api/admin/me`, 401 → редирект на логин.
- Dev: Vite `server.proxy` `/api` → `localhost:8000`.
- Ссылки «Купить»: `target="_blank" rel="noopener nofollow"`.

## Хранилище фото (S3)

Фото китов загружаются файлами в **S3-совместимое** хранилище (`app/services/storage.py`,
boto3; sync-вызовы в async-эндпоинтах через `run_in_threadpool`). Загрузка идёт через бэк
(multipart) — валидация типа/размера/лимита и запись в БД на сервере; в `kit_images` хранится
только `object_key`. Отдача — по **стабильному публичному URL** `{S3_PUBLIC_BASE_URL}/{key}`
(витрина читает `kit.image_url` как обычную ссылку; presigned истёк бы), поэтому бакет должен
допускать public-read (или отдаваться через CDN). Обложка кита — `kit.image_url`: первое
загруженное фото проставляется автоматически, любое можно назначить обложкой; при удалении
обложки она переназначается на следующее фото. Настройки — `S3_*` в `config.py`/`.env`.
В тестах S3-слой мокается (`monkeypatch`), реальное хранилище не требуется.

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
