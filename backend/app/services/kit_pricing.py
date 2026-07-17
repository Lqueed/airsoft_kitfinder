"""Расчёт цены кита и подбор вариантов flexible-позиций.

Единственный источник правды по ценам кита — цены не денормализуются, всегда
считаются из активных офверов в наличии. Используется админ-предпросмотром,
публичным каталогом и деталкой, визардом.

Модель вилки цены:
- цена позиции = минимальная цена покупки (самый дешёвый магазин среди активных
  офферов в наличии) конкретного товара;
- fixed-позиция даёт фиксированную цену (один товар);
- flexible-позиция даёт диапазон [самый дешёвый вариант; самый дорогой вариант];
- `price_min` — сумма по ОБЯЗАТЕЛЬНЫМ позициям, когда во всех flexible берём самый
  дешёвый вариант;
- `price_max` — сумма по обязательным (самый дорогой вариант) ПЛЮС опциональные
  позиции, у которых есть доступная цена (максимальная комплектация);
- полнота (`complete`) и сама вилка определяются только по обязательным позициям:
  если у обязательной позиции нет доступной цены (нет офферов/вариантов), кит
  помечается неполным (`complete=False`), а суммарная вилка не считается (None).
"""

from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import KitItem, KitItemCandidate, Offer, Product
from app.models.enums import KitItemType


@dataclass(slots=True)
class ItemPricing:
    """Цена одной позиции кита."""

    item_id: int
    title: str
    item_type: KitItemType
    is_required: bool
    min_price: Decimal | None  # None = нет доступного товара/варианта с ценой
    max_price: Decimal | None
    variant_count: int = 0  # число доступных вариантов (для flexible)


@dataclass(slots=True)
class KitPricing:
    """Вилка цены кита и разбивка по позициям."""

    price_min: Decimal | None  # None, если хотя бы одна обязательная позиция недоступна
    price_max: Decimal | None
    complete: bool  # все обязательные позиции имеют доступную цену
    items: list[ItemPricing] = field(default_factory=list)


async def product_min_price(session: AsyncSession, product_id: int) -> Decimal | None:
    """Минимальная цена покупки товара: дешёвейший активный оффер в наличии.

    None — если у товара нет активных офферов в наличии с указанной ценой.
    """
    return await session.scalar(
        select(func.min(Offer.price)).where(
            Offer.product_id == product_id,
            Offer.is_active.is_(True),
            Offer.in_stock.is_(True),
            Offer.price.is_not(None),
        )
    )


async def flexible_variants(session: AsyncSession, item: KitItem) -> list[Product]:
    """Товары-варианты flexible-позиции: (по критериям ∪ pinned) − excluded.

    Критерии: категория позиции, `attr_filters` (подмножество совпадает с
    `Product.attrs`), `max_price` (по минимальной цене покупки товара).
    Возвращаются только товары, у которых есть доступная цена.
    """
    if item.item_type is not KitItemType.FLEXIBLE or item.category_id is None:
        return []

    pinned, excluded = await _curated_ids(session, item.id)

    # Кандидаты по категории + JSONB-фильтру атрибутов, плюс явно закреплённые.
    stmt = select(Product).where(Product.category_id == item.category_id)
    if item.attr_filters:
        stmt = stmt.where(Product.attrs.contains(item.attr_filters))
    by_criteria = set((await session.scalars(stmt)).all())

    if pinned:
        pinned_products = (
            await session.scalars(select(Product).where(Product.id.in_(pinned)))
        ).all()
        by_criteria.update(pinned_products)

    variants: list[Product] = []
    for product in by_criteria:
        if product.id in excluded:
            continue
        price = await product_min_price(session, product.id)
        if price is None:
            continue  # нет доступного оффера — вариант недоступен
        if item.max_price is not None and price > item.max_price and product.id not in pinned:
            continue  # дороже лимита (закреплённые не режем по цене)
        variants.append(product)
    return variants


async def _curated_ids(session: AsyncSession, item_id: int) -> tuple[set[int], set[int]]:
    """Множества закреплённых (pinned) и исключённых (excluded) товаров позиции."""
    rows = (
        await session.scalars(
            select(KitItemCandidate).where(KitItemCandidate.kit_item_id == item_id)
        )
    ).all()
    pinned = {c.product_id for c in rows if c.is_pinned}
    excluded = {c.product_id for c in rows if c.is_excluded}
    return pinned, excluded


async def price_item(session: AsyncSession, item: KitItem) -> ItemPricing:
    """Считает цену одной позиции (fixed — фикс, flexible — диапазон вариантов)."""
    if item.item_type is KitItemType.FIXED:
        price = (
            await product_min_price(session, item.product_id)
            if item.product_id is not None
            else None
        )
        return ItemPricing(
            item_id=item.id,
            title=item.title,
            item_type=item.item_type,
            is_required=item.is_required,
            min_price=price,
            max_price=price,
            variant_count=1 if price is not None else 0,
        )

    variants = await flexible_variants(session, item)
    raw_prices = [await product_min_price(session, v.id) for v in variants]
    prices = [p for p in raw_prices if p is not None]
    return ItemPricing(
        item_id=item.id,
        title=item.title,
        item_type=item.item_type,
        is_required=item.is_required,
        min_price=min(prices) if prices else None,
        max_price=max(prices) if prices else None,
        variant_count=len(prices),
    )


async def price_kit(session: AsyncSession, items: list[KitItem]) -> KitPricing:
    """Вилка цены кита: min — по обязательным, max — по обязательным + опциональные."""
    priced = [await price_item(session, item) for item in items]

    required = [p for p in priced if p.is_required]
    optional = [p for p in priced if not p.is_required]
    complete = all(p.min_price is not None for p in required)

    if not complete:
        return KitPricing(price_min=None, price_max=None, complete=False, items=priced)

    price_min = sum((p.min_price for p in required), Decimal(0))
    # В верх вилки добавляем опциональные позиции с доступной ценой (макс. комплектация).
    price_max = sum((p.max_price for p in required), Decimal(0)) + sum(
        (p.max_price for p in optional if p.max_price is not None), Decimal(0)
    )
    return KitPricing(price_min=price_min, price_max=price_max, complete=True, items=priced)
