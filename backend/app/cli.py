"""CLI-команды: seed справочников, генерация хеша пароля админа, парсинг магазинов.

Запуск: `uv run python -m app.cli <команда>`.
"""

import argparse
import asyncio

from sqlalchemy import select

from app.auth import hash_password
from app.db import SessionLocal
from app.models.catalog import Category
from app.parsers.registry import PARSERS, get_parser
from app.services.ingest import ingest_shop

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
    """Запускает парсинг указанных магазинов (или всех, если список пуст)."""
    targets = codes or list(PARSERS)
    for code in targets:
        parser_cls = get_parser(code)
        print(f"[{code}] старт парсинга…")
        async with SessionLocal() as session:
            report = await ingest_shop(session, parser_cls(), limit=limit)
        print(
            f"[{code}] {report.status}: распарсено={report.total_parsed} "
            f"новых={report.created} обновлено={report.updated} "
            f"изм.цен={report.price_changes} реактив.={report.reactivated} "
            f"деактив.={report.deactivated}"
            + (f" — {report.message}" if report.message else "")
        )


def main() -> None:
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

    args = parser.parse_args()

    if args.command == "seed":
        asyncio.run(seed_categories())
    elif args.command == "hash-password":
        gen_password_hash(args.password)
    elif args.command == "parse":
        asyncio.run(parse_shops(args.shops, args.limit))


if __name__ == "__main__":
    main()
