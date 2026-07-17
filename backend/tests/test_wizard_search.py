"""API-тесты визарда (скоринг) и поиска (pg_trgm)."""

from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import Kit, KitItem, Offer, Product, Shop
from app.models.enums import KitItemType, KitStatus


async def _shop(session: AsyncSession) -> int:
    existing = await session.scalar(select(Shop.id).where(Shop.code == "ws_shop"))
    if existing is not None:
        return existing
    shop = Shop(code="ws_shop", name="WS Shop", base_url="https://ws.test")
    session.add(shop)
    await session.flush()
    return shop.id


async def _product(session: AsyncSession, name: str) -> Product:
    product = Product(name=name, slug=name, match_key=name)
    session.add(product)
    await session.flush()
    return product


async def _offer(session: AsyncSession, shop_id: int, product_id: int, price: Decimal) -> None:
    session.add(
        Offer(
            shop_id=shop_id, product_id=product_id, external_id=f"{product_id}-{price}",
            url="https://ws.test/p", raw_title="t", price=price, in_stock=True, is_active=True,
        )
    )
    await session.flush()


async def _kit(
    session: AsyncSession, name: str, *, role: str | None = None, published: bool = True
) -> Kit:
    kit = Kit(
        slug=name, name=name, role=role,
        status=KitStatus.PUBLISHED if published else KitStatus.DRAFT,
    )
    session.add(kit)
    await session.flush()
    return kit


async def _fixed(session: AsyncSession, kit_id: int, product_id: int) -> None:
    session.add(
        KitItem(kit_id=kit_id, item_type=KitItemType.FIXED, title="Позиция",
                is_required=True, product_id=product_id)
    )
    await session.flush()


async def _priced_kit(
    session: AsyncSession, name: str, price: Decimal, *, role: str | None = None
) -> Kit:
    shop = await _shop(session)
    kit = await _kit(session, name, role=role)
    product = await _product(session, f"{name}-товар")
    await _offer(session, shop, product.id, price)
    await _fixed(session, kit.id, product.id)
    return kit


def _index(cards: list[dict], kit_id: int) -> int | None:
    for i, c in enumerate(cards):
        if c["id"] == kit_id:
            return i
    return None


# --- Визард -----------------------------------------------------------------


async def test_wizard_ranks_affordable_above_expensive(
    client: AsyncClient, session: AsyncSession
) -> None:
    cheap = await _priced_kit(session, "ws-cheap", Decimal(500))
    pricey = await _priced_kit(session, "ws-pricey", Decimal(50000))

    resp = await client.post("/api/wizard/recommend", json={"budget": 1000})
    assert resp.status_code == 200
    cards = resp.json()
    i_cheap, i_pricey = _index(cards, cheap.id), _index(cards, pricey.id)
    assert i_cheap is not None and i_pricey is not None
    assert i_cheap < i_pricey  # в бюджете выше сильно дороже


async def test_wizard_role_bonus_reorders(
    client: AsyncClient, session: AsyncSession
) -> None:
    assault = await _priced_kit(session, "ws-assault", Decimal(1000), role="assault")
    sniper = await _priced_kit(session, "ws-sniper", Decimal(1000), role="sniper")

    resp = await client.post("/api/wizard/recommend", json={"role": "assault", "budget": 2000})
    cards = resp.json()
    assert _index(cards, assault.id) < _index(cards, sniper.id)


async def test_wizard_skips_incomplete_kit(
    client: AsyncClient, session: AsyncSession
) -> None:
    kit = await _kit(session, "ws-incomplete")
    product = await _product(session, "ws-no-offers")  # без офферов → неполный
    await _fixed(session, kit.id, product.id)

    resp = await client.post("/api/wizard/recommend", json={})
    assert _index(resp.json(), kit.id) is None


# --- Поиск ------------------------------------------------------------------


async def test_search_by_kit_name(client: AsyncClient, session: AsyncSession) -> None:
    kit = await _priced_kit(session, "Уникальный штурмовой набор Квазар", Decimal(1000))

    resp = await client.get("/api/search", params={"q": "Квазар"})
    assert resp.status_code == 200
    assert _index(resp.json(), kit.id) is not None


async def test_search_tolerates_typo(client: AsyncClient, session: AsyncSession) -> None:
    kit = await _priced_kit(session, "Набор Абракадабра", Decimal(1000))

    resp = await client.get("/api/search", params={"q": "абракадбра"})  # опечатка
    assert _index(resp.json(), kit.id) is not None


async def test_search_by_composition_product(client: AsyncClient, session: AsyncSession) -> None:
    shop = await _shop(session)
    kit = await _kit(session, "ws-by-composition")
    product = await _product(session, "Маска Зорбтех Про")  # уникальный бренд
    await _offer(session, shop, product.id, Decimal(1500))
    await _fixed(session, kit.id, product.id)

    resp = await client.get("/api/search", params={"q": "Зорбтех"})
    assert _index(resp.json(), kit.id) is not None


async def test_search_min_length(client: AsyncClient) -> None:
    resp = await client.get("/api/search", params={"q": "a"})
    assert resp.status_code == 422
