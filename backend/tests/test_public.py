"""API-тесты публичной витрины: каталог (фильтры, published) и деталка кита."""

from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import Category, Kit, KitItem, Offer, Product, Shop
from app.models.enums import KitItemType, KitStatus


async def _shop(session: AsyncSession) -> int:
    existing = await session.scalar(select(Shop.id).where(Shop.code == "pub_shop"))
    if existing is not None:
        return existing
    shop = Shop(code="pub_shop", name="Pub Shop", base_url="https://pub.test")
    session.add(shop)
    await session.flush()
    return shop.id


async def _product(session: AsyncSession, name: str, category_id: int | None = None) -> Product:
    product = Product(name=name, slug=name, match_key=name, category_id=category_id)
    session.add(product)
    await session.flush()
    return product


async def _offer(session: AsyncSession, shop_id: int, product_id: int, price: Decimal) -> None:
    session.add(
        Offer(
            shop_id=shop_id, product_id=product_id, external_id=f"{product_id}-{price}",
            url=f"https://pub.test/{product_id}", raw_title="t", price=price,
            in_stock=True, is_active=True,
        )
    )
    await session.flush()


async def _category(session: AsyncSession, slug: str) -> int:
    existing = await session.scalar(select(Category.id).where(Category.slug == slug))
    if existing is not None:
        return existing
    cat = Category(slug=slug, name=slug)
    session.add(cat)
    await session.flush()
    return cat.id


async def _kit(
    session: AsyncSession, name: str, *, role: str | None = None, published: bool = True
) -> Kit:
    kit = Kit(
        slug=name,
        name=name,
        role=role,
        status=KitStatus.PUBLISHED if published else KitStatus.DRAFT,
    )
    session.add(kit)
    await session.flush()
    return kit


async def _fixed(session: AsyncSession, kit_id: int, product_id: int) -> None:
    session.add(
        KitItem(
            kit_id=kit_id, item_type=KitItemType.FIXED, title="Позиция",
            is_required=True, product_id=product_id,
        )
    )
    await session.flush()


async def _flexible(session: AsyncSession, kit_id: int, category_id: int) -> KitItem:
    item = KitItem(
        kit_id=kit_id, item_type=KitItemType.FLEXIBLE, title="Гибкая",
        is_required=True, category_id=category_id,
    )
    session.add(item)
    await session.flush()
    return item


async def _priced_kit(
    session: AsyncSession, name: str, price: Decimal, *, role: str | None = None
) -> Kit:
    """Опубликованный кит с одной fixed-позицией известной цены."""
    shop = await _shop(session)
    kit = await _kit(session, name, role=role)
    product = await _product(session, f"{name}-товар")
    await _offer(session, shop, product.id, price)
    await _fixed(session, kit.id, product.id)
    return kit


async def test_catalog_shows_only_published(client: AsyncClient, session: AsyncSession) -> None:
    pub = await _priced_kit(session, "pub-kit", Decimal(1000))
    draft = await _kit(session, "draft-kit", published=False)

    resp = await client.get("/api/kits")
    assert resp.status_code == 200
    ids = {c["id"] for c in resp.json()["items"]}
    assert pub.id in ids
    assert draft.id not in ids


async def test_catalog_filter_by_role(client: AsyncClient, session: AsyncSession) -> None:
    sniper = await _priced_kit(session, "sniper-kit", Decimal(1000), role="sniper")
    assault = await _priced_kit(session, "assault-kit", Decimal(1000), role="assault")

    resp = await client.get("/api/kits", params={"role": "sniper"})
    ids = {c["id"] for c in resp.json()["items"]}
    assert sniper.id in ids
    assert assault.id not in ids


async def test_catalog_budget_intersection(client: AsyncClient, session: AsyncSession) -> None:
    cheap = await _priced_kit(session, "cheap-kit", Decimal(500), role="dmr")
    pricey = await _priced_kit(session, "pricey-kit", Decimal(5000), role="dmr")

    within = await client.get("/api/kits", params={"role": "dmr", "budget_max": "1000"})
    ids = {c["id"] for c in within.json()["items"]}
    assert cheap.id in ids and pricey.id not in ids

    above = await client.get("/api/kits", params={"role": "dmr", "budget_min": "3000"})
    ids2 = {c["id"] for c in above.json()["items"]}
    assert pricey.id in ids2 and cheap.id not in ids2


async def test_detail_fixed_offers_sorted(client: AsyncClient, session: AsyncSession) -> None:
    shop = await _shop(session)
    kit = await _kit(session, "detail-fixed")
    product = await _product(session, "Очки деталь")
    await _offer(session, shop, product.id, Decimal(900))
    await _offer(session, shop, product.id, Decimal(700))  # дешевле
    await _fixed(session, kit.id, product.id)

    resp = await client.get("/api/kits/detail-fixed")
    assert resp.status_code == 200
    item = resp.json()["items"][0]
    assert item["product"]["name"] == "Очки деталь"
    prices = [float(o["price"]) for o in item["offers"]]
    assert prices == [700.0, 900.0]  # от дешёвого к дорогому


async def test_detail_flexible_variants(client: AsyncClient, session: AsyncSession) -> None:
    shop = await _shop(session)
    cat = await _category(session, "pub_flex_cat")
    kit = await _kit(session, "detail-flex")
    p1 = await _product(session, "Вариант A", cat)
    p2 = await _product(session, "Вариант B", cat)
    await _offer(session, shop, p1.id, Decimal(200))
    await _offer(session, shop, p2.id, Decimal(400))
    await _flexible(session, kit.id, cat)

    resp = await client.get("/api/kits/detail-flex")
    item = resp.json()["items"][0]
    assert item["item_type"] == "flexible"
    variant_prices = [float(v["min_price"]) for v in item["variants"]]
    assert variant_prices == [200.0, 400.0]


async def test_detail_draft_returns_404(client: AsyncClient, session: AsyncSession) -> None:
    await _kit(session, "hidden-draft", published=False)
    resp = await client.get("/api/kits/hidden-draft")
    assert resp.status_code == 404
