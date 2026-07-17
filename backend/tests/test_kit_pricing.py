"""Тесты расчёта вилки цены кита (services/kit_pricing)."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import Category, Kit, KitItem, Offer, Product, Shop
from app.models.enums import KitItemType, KitStatus
from app.services.kit_pricing import price_kit


async def _shop(session: AsyncSession) -> int:
    shop = Shop(code="pricing_shop", name="s", base_url="https://s.test")
    session.add(shop)
    await session.flush()
    return shop.id


async def _category(session: AsyncSession, slug: str) -> int:
    """Get-or-create категории (в тестовой БД мог остаться seed)."""
    existing = await session.scalar(select(Category.id).where(Category.slug == slug))
    if existing is not None:
        return existing
    cat = Category(slug=slug, name=slug)
    session.add(cat)
    await session.flush()
    return cat.id


async def _product(session: AsyncSession, name: str, category_id: int | None = None) -> Product:
    product = Product(name=name, slug=name, match_key=name, category_id=category_id)
    session.add(product)
    await session.flush()
    return product


async def _offer(
    session: AsyncSession,
    shop_id: int,
    product_id: int,
    price: Decimal,
    *,
    in_stock: bool = True,
    is_active: bool = True,
) -> None:
    session.add(
        Offer(
            shop_id=shop_id,
            product_id=product_id,
            external_id=f"{product_id}-{price}",
            url="https://x",
            raw_title="t",
            price=price,
            in_stock=in_stock,
            is_active=is_active,
        )
    )
    await session.flush()


async def _kit(session: AsyncSession) -> int:
    kit = Kit(slug="k", name="k", status=KitStatus.DRAFT)
    session.add(kit)
    await session.flush()
    return kit.id


async def _fixed_item(
    session: AsyncSession, kit_id: int, product_id: int, *, required: bool = True
) -> KitItem:
    item = KitItem(
        kit_id=kit_id, item_type=KitItemType.FIXED, title="fx",
        is_required=required, product_id=product_id,
    )
    session.add(item)
    await session.flush()
    return item


async def _flexible_item(
    session: AsyncSession, kit_id: int, category_id: int, *, required: bool = True
) -> KitItem:
    item = KitItem(
        kit_id=kit_id, item_type=KitItemType.FLEXIBLE, title="fl",
        is_required=required, category_id=category_id,
    )
    session.add(item)
    await session.flush()
    return item


async def test_fixed_item_takes_cheapest_offer(session: AsyncSession) -> None:
    shop = await _shop(session)
    kit = await _kit(session)
    product = await _product(session, "goggles")
    await _offer(session, shop, product.id, Decimal(150))
    await _offer(session, shop, product.id, Decimal(100))  # дешевле — его и берём
    item = await _fixed_item(session, kit, product.id)

    pricing = await price_kit(session, [item])
    assert pricing.complete is True
    assert pricing.price_min == Decimal(100)
    assert pricing.price_max == Decimal(100)


async def test_fixed_item_ignores_inactive_and_out_of_stock(session: AsyncSession) -> None:
    shop = await _shop(session)
    kit = await _kit(session)
    product = await _product(session, "helmet")
    await _offer(session, shop, product.id, Decimal(50), is_active=False)  # неактивен
    await _offer(session, shop, product.id, Decimal(60), in_stock=False)  # нет в наличии
    await _offer(session, shop, product.id, Decimal(200))  # единственный валидный
    item = await _fixed_item(session, kit, product.id)

    pricing = await price_kit(session, [item])
    assert pricing.price_min == Decimal(200)


async def test_flexible_item_is_a_range_over_variants(session: AsyncSession) -> None:
    shop = await _shop(session)
    kit = await _kit(session)
    cat = await _category(session, "pricing_flex_range")
    cheap = await _product(session, "bbs-cheap", cat)
    pricey = await _product(session, "bbs-pricey", cat)
    await _offer(session, shop, cheap.id, Decimal(200))
    await _offer(session, shop, pricey.id, Decimal(500))
    item = await _flexible_item(session, kit, cat)

    pricing = await price_kit(session, [item])
    assert pricing.complete is True
    assert pricing.price_min == Decimal(200)
    assert pricing.price_max == Decimal(500)
    assert pricing.items[0].variant_count == 2


async def test_optional_item_lifts_only_max(session: AsyncSession) -> None:
    shop = await _shop(session)
    kit = await _kit(session)
    cat = await _category(session, "pricing_flex_opt")
    required_product = await _product(session, "req-goggles")
    await _offer(session, shop, required_product.id, Decimal(100))
    cheap = await _product(session, "opt-cheap", cat)
    pricey = await _product(session, "opt-pricey", cat)
    await _offer(session, shop, cheap.id, Decimal(200))
    await _offer(session, shop, pricey.id, Decimal(500))

    required = await _fixed_item(session, kit, required_product.id, required=True)
    optional = await _flexible_item(session, kit, cat, required=False)

    pricing = await price_kit(session, [required, optional])
    # min — только обязательная; max — обязательная + самый дорогой опциональный вариант
    assert pricing.price_min == Decimal(100)
    assert pricing.price_max == Decimal(600)


async def test_required_item_without_offers_makes_kit_incomplete(session: AsyncSession) -> None:
    kit = await _kit(session)
    product = await _product(session, "no-offers")  # нет ни одного оффера
    item = await _fixed_item(session, kit, product.id, required=True)

    pricing = await price_kit(session, [item])
    assert pricing.complete is False
    assert pricing.price_min is None
    assert pricing.price_max is None


async def test_kit_with_only_optional_items_is_complete(session: AsyncSession) -> None:
    shop = await _shop(session)
    kit = await _kit(session)
    product = await _product(session, "opt-only")
    await _offer(session, shop, product.id, Decimal(300))
    optional = await _fixed_item(session, kit, product.id, required=False)

    pricing = await price_kit(session, [optional])
    assert pricing.complete is True
    assert pricing.price_min == Decimal(0)
    assert pricing.price_max == Decimal(300)
