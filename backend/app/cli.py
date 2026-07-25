"""CLI-команды: seed справочников, генерация хеша пароля админа, парсинг магазинов.

Запуск: `uv run python -m app.cli <команда>`.
"""

import argparse
import asyncio
import logging
import re
import sys
from collections.abc import Coroutine
from typing import Any

from sqlalchemy import select

from app.auth import hash_password
from app.config import settings
from app.db import SessionLocal
from app.models.catalog import Category, Offer, Shop
from app.parsers.registry import PARSERS, get_parser
from app.services.ingest import ingest_shop
from app.services.llm_extract import (
    ExtractionCache,
    GigaChatSession,
    drive_key,
    extract_drive,
)
from app.services.matching import build_match_key, guess_category_slug, match_unmatched

log = logging.getLogger("app.cli")

# Базовая таксономия категорий товаров (slug → отображаемое имя)
BASE_CATEGORIES: list[tuple[str, str]] = [
    ("drive", "Привод"),
    ("eyewear", "Защита глаз (маски, очки)"),
    ("face_protection", "Защита лица"),
    ("helmet", "Шлем"),
    ("uniform", "Форма"),
    ("rig", "Разгрузка / жилет"),
    ("boots", "Обувь"),
    ("gloves", "Перчатки"),
    ("knee_pads", "Наколенники / налокотники"),
    ("battery", "Батарея / зарядка"),
    ("magazines", "Магазины"),
    ("bbs", "Шары"),
    ("grenades", "Гранаты"),
    ("radio", "Связь / рация"),
    ("pouches", "Подсумки"),
    ("accessories", "Аксессуары"),
]


async def seed_categories() -> None:
    """Идемпотентно создаёт базовые категории (upsert по slug)."""
    async with SessionLocal() as session:
        existing = set(
            (await session.scalars(select(Category.slug))).all()
        )
        created = 0
        for slug, name in BASE_CATEGORIES:
            if slug not in existing:
                session.add(Category(slug=slug, name=name))
                created += 1
        await session.commit()
        print(f"Категории: создано {created}, всего в справочнике {len(BASE_CATEGORIES)}")


def gen_password_hash(password: str) -> None:
    """Печатает bcrypt-хеш пароля для ADMIN_PASSWORD_HASH в .env."""
    print(hash_password(password))


async def parse_shops(codes: list[str], limit: int | None = None) -> None:
    """Запускает парсинг магазинов (или всех). Падение одного не роняет остальных."""
    targets = codes or list(PARSERS)
    for code in targets:
        try:
            parser_cls = get_parser(code)
            async with SessionLocal() as session:
                report = await ingest_shop(session, parser_cls(), limit=limit)
            log.info(
                "[%s] %s: распарсено=%d новых=%d обновлено=%d изм.цен=%d "
                "реактив.=%d деактив.=%d%s",
                code,
                report.status,
                report.total_parsed,
                report.created,
                report.updated,
                report.price_changes,
                report.reactivated,
                report.deactivated,
                f" — {report.message}" if report.message else "",
            )
        except Exception:  # один магазин упал — логируем и идём к следующему
            log.exception("[%s] парсинг упал — пропускаю магазин", code)


async def rematch(shop_code: str | None = None) -> None:
    """Матчит офферы без товара в канонические products."""
    async with SessionLocal() as session:
        shop_id: int | None = None
        if shop_code:
            shop_id = await session.scalar(select(Shop.id).where(Shop.code == shop_code))
            if shop_id is None:
                print(f"Магазин '{shop_code}' не найден")
                return
        report = await match_unmatched(session, shop_id=shop_id)
    print(
        f"Матчинг: обработано={report.processed} "
        f"новых товаров={report.created_products} "
        f"привязано к существующим={report.linked_existing}"
    )


# Грубый префильтр «это готовый привод, а не запчасть» — экономит вызовы API.
# LLM (is_drive) остаётся точным фильтром; регулярки лишь отсекают явный обвес.
_DRIVE_INCLUDE = re.compile(
    r"(страйкбольн\w*\s+(автомат|пистолет|винтовк|пулем[её]т|дробовик|карабин|ружь)"
    r"|электро(пистолет|автомат|привод)|\bпривод\b|\baeg\b|\bgbbr?\b|\baep\b)",
    re.IGNORECASE,
)
_DRIVE_EXCLUDE = re.compile(
    r"(набор|рукоят|крепл|антабк|переходник|поршень|\bцпг\b|тюнинг|прицел|магазин"
    r"|подсумок|ствол|резинк|аккумулятор|\bручка\b|фонар|глушит|батаре|зарядн|чехол"
    r"|сошк|планк|шестерн|\bмотор|гирбокс|hop|хоп|шептал|цилиндр)",
    re.IGNORECASE,
)


def _looks_like_drive(title: str) -> bool:
    """Грубый признак готового привода: есть include-маркер и нет обвес-маркера."""
    return bool(_DRIVE_INCLUDE.search(title)) and not _DRIVE_EXCLUDE.search(title)


async def llm_extract_spike(category: str, limit: int, scan: int, dry: bool) -> None:
    """Спайк: LLM-экстракция атрибутов и замер авто-склейки против токен-ключа.

    Недеструктивно (в products не пишет). Берёт активные офферы указанной
    категории, извлекает атрибуты через Gemini (с файловым кэшем), строит
    предлагаемый структурный ключ и сравнивает: во сколько кластеров склеились
    офферы по новому ключу против текущего `build_match_key`.
    """
    if not settings.gigachat_auth_key:
        print("Не задан GIGACHAT_AUTH_KEY в .env — экстракция невозможна.")
        return
    if category != "drive":
        print("Спайк реализован только для категории 'drive'.")
        return

    # Тянем офферы в память заранее, чтобы не держать соединение с БД во время
    # долгих вызовов API. Категорию определяем той же эвристикой, что и матчинг.
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(
                    Offer.raw_title, Offer.raw_category, Offer.shop_id
                ).where(Offer.is_active)
            )
        ).all()

    selected: list[tuple[str, int]] = []  # (raw_title, shop_id)
    scanned = 0
    for raw_title, raw_category, shop_id in rows:
        if scanned >= scan or len(selected) >= limit:
            break
        scanned += 1
        if guess_category_slug(raw_category, raw_title) == category and _looks_like_drive(
            raw_title
        ):
            selected.append((raw_title, shop_id))

    if dry:
        by_shop: dict[int, int] = {}
        for _, shop_id in selected:
            by_shop[shop_id] = by_shop.get(shop_id, 0) + 1
        print(
            f"[dry] выборка '{category}': {len(selected)} офферов "
            f"(просканировано {scanned}); по магазинам: {by_shop}"
        )
        for title, shop_id in selected[:15]:
            print(f"    [shop {shop_id}] {title}")
        print("\nБез вызовов GigaChat. Для запуска экстракции убери --dry.")
        return

    cache = ExtractionCache(settings.llm_cache_path)
    # (proposed_key -> набор (title, shop_id)); current_keys — множество токен-ключей
    clusters: dict[str, list[tuple[str, int]]] = {}
    current_keys: set[str] = set()
    fallback = 0

    print(
        f"[llm-extract] отобрано {len(selected)} офферов '{category}' "
        f"(просканировано {scanned})…"
    )
    async with GigaChatSession() as session:
        for raw_title, shop_id in selected:
            current_keys.add(build_match_key(raw_title, category)[0])
            attrs = await extract_drive(session, cache, raw_title)
            key = drive_key(attrs)
            if key is None:
                fallback += 1
                continue
            clusters.setdefault(key, []).append((raw_title, shop_id))
    cache.save()

    matched = len(selected) - fallback
    cross_shop = {k: v for k, v in clusters.items() if len({s for _, s in v}) >= 2}
    print(
        f"\n=== Итог спайка ({category}) ===\n"
        f"офферов в выборке:        {len(selected)}\n"
        f"кэш: попаданий={cache.hits} промахов (вызовов API)={cache.misses}\n"
        f"распознано приводов:      {matched}\n"
        f"ушло на фолбэк (не LLM):  {fallback}\n"
        f"--- кластеризация распознанных ---\n"
        f"текущий токен-ключ:       {len(current_keys)} кластеров\n"
        f"предлагаемый LLM-ключ:    {len(clusters)} кластеров\n"
        f"из них кросс-магазинных:  {len(cross_shop)} (склеили офферы ≥2 магазинов)"
    )
    if cross_shop:
        print("\nПримеры кросс-магазинных склеек (ключ → названия):")
        for key, members in sorted(cross_shop.items(), key=lambda kv: -len(kv[1]))[:8]:
            print(f"  {key}")
            for title, shop_id in members[:5]:
                print(f"    [shop {shop_id}] {title}")


def _run(coro: Coroutine[Any, Any, None]) -> None:
    """asyncio.run с SelectorEventLoop на Windows.

    async-psycopg несовместим с дефолтным ProactorEventLoop на Windows.
    На Linux/кроне ветка не задействуется — обычный asyncio.run.
    """
    if sys.platform == "win32":
        asyncio.run(coro, loop_factory=asyncio.SelectorEventLoop)
    else:
        asyncio.run(coro)


def main() -> None:
    # Логи парсеров/ingest в stderr с временем — видно, что прогон жив
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )
    parser = argparse.ArgumentParser(prog="app.cli", description="Служебные команды kitfinder")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("seed", help="Заполнить справочник категорий")

    hash_parser = sub.add_parser("hash-password", help="Сгенерировать bcrypt-хеш пароля админа")
    hash_parser.add_argument("password", help="Пароль в открытом виде")

    parse_parser = sub.add_parser("parse", help="Спарсить магазины и обновить офферы")
    parse_parser.add_argument(
        "--shop",
        action="append",
        dest="shops",
        default=[],
        help="Код магазина (можно повторять). Без флага — все магазины.",
    )
    parse_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Ограничить число офферов (smoke-прогон; деактивация пропускается).",
    )

    rematch_parser = sub.add_parser("rematch", help="Сматчить офферы без товара в products")
    rematch_parser.add_argument(
        "--shop", default=None, help="Код магазина (по умолчанию — все несматченные)."
    )

    llm_parser = sub.add_parser(
        "llm-extract", help="Спайк: LLM-экстракция атрибутов и замер авто-склейки (dry-run)"
    )
    llm_parser.add_argument("--category", default="drive", help="Категория (пока только drive).")
    llm_parser.add_argument(
        "--limit", type=int, default=200, help="Сколько офферов извлечь (лимит вызовов API)."
    )
    llm_parser.add_argument(
        "--scan", type=int, default=4000, help="Сколько активных офферов просканировать."
    )
    llm_parser.add_argument(
        "--dry", action="store_true", help="Только показать выборку, без вызовов GigaChat."
    )

    args = parser.parse_args()

    if args.command == "seed":
        _run(seed_categories())
    elif args.command == "hash-password":
        gen_password_hash(args.password)
    elif args.command == "parse":
        _run(parse_shops(args.shops, args.limit))
    elif args.command == "rematch":
        _run(rematch(args.shop))
    elif args.command == "llm-extract":
        _run(llm_extract_spike(args.category, args.limit, args.scan, args.dry))


if __name__ == "__main__":
    main()
