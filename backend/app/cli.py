"""CLI-команды: seed справочников и генерация хеша пароля админа.

Запуск: `uv run python -m app.cli <команда>`.
Команда `parse` (парсинг магазинов) добавится на этапе M2.
"""

import argparse
import asyncio

from sqlalchemy import select

from app.auth import hash_password
from app.db import SessionLocal
from app.models.catalog import Category

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


def main() -> None:
    parser = argparse.ArgumentParser(prog="app.cli", description="Служебные команды kitfinder")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("seed", help="Заполнить справочник категорий")

    hash_parser = sub.add_parser("hash-password", help="Сгенерировать bcrypt-хеш пароля админа")
    hash_parser.add_argument("password", help="Пароль в открытом виде")

    args = parser.parse_args()

    if args.command == "seed":
        asyncio.run(seed_categories())
    elif args.command == "hash-password":
        gen_password_hash(args.password)


if __name__ == "__main__":
    main()
