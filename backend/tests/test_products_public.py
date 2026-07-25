"""API-тесты умного поиска по товарам и карточки сравнения цен (M9)."""

from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import Offer, Product, Shop


async def _shop(session: AsyncSession, code: str) -> int:
    existing = await session.scalar(select(Shop.id).where(Shop.code == code))
    if existing is not None:
        return existing
    shop = Shop(code=code, name=f"Shop {code}", base_url=f"https://{code}.test")
    session.add(shop)
    await session.flush()
    return shop.id


async def _product(session: AsyncSession, name: str) -> Product:
    product = Product(name=name, slug=name, match_key=name)
    session.add(product)
    await session.flush()
    return product


async def _offer(
    session: AsyncSession,
    shop_id: int,
    product_id: int,
    price: Decimal | None,
    *,
    in_stock: bool = True,
    is_active: bool = True,
) -> None:
    session.add(
        Offer(
            shop_id=shop_id,
            product_id=product_id,
            external_id=f"{shop_id}-{product_id}-{price}",
            url=f"https://shop.test/p/{product_id}",
            raw_title="t",
            price=price,
            in_stock=in_stock,
            is_active=is_active,
        )
    )
    await session.flush()


def _row(items: list[dict], product_id: int) -> dict | None:
    return next((i for i in items if i["id"] == product_id), None)


# --- Поиск ------------------------------------------------------------------


async def test_search_finds_available_product(client: AsyncClient, session: AsyncSession) -> None:
    shop = await _shop(session, "pp_a")
    product = await _product(session, "Привод Каракурт Спектр")
    await _offer(session, shop, product.id, Decimal(9000))

    resp = await client.get("/api/products/search", params={"q": "Каракурт"})
    assert resp.status_code == 200
    row = _row(resp.json()["items"], product.id)
    assert row is not None
    assert row["shops_count"] == 1
    assert Decimal(row["price_min"]) == Decimal(9000)


async def test_search_tolerates_typo(client: AsyncClient, session: AsyncSession) -> None:
    shop = await _shop(session, "pp_b")
    product = await _product(session, "Маска Абракадабра Тактикал")
    await _offer(session, shop, product.id, Decimal(1500))

    resp = await client.get("/api/products/search", params={"q": "абракадбра"})  # опечатка
    assert _row(resp.json()["items"], product.id) is not None


async def test_search_min_price_across_shops(client: AsyncClient, session: AsyncSession) -> None:
    a = await _shop(session, "pp_c1")
    b = await _shop(session, "pp_c2")
    product = await _product(session, "Пистолет Уникум Кроссфайр")
    await _offer(session, a, product.id, Decimal(7000))
    await _offer(session, b, product.id, Decimal(5500))  # дешевле

    row = _row(
        (await client.get("/api/products/search", params={"q": "Кроссфайр"})).json()["items"],
        product.id,
    )
    assert row["shops_count"] == 2
    assert Decimal(row["price_min"]) == Decimal(5500)  # минимальная из двух


async def test_search_excludes_unavailable(client: AsyncClient, session: AsyncSession) -> None:
    shop = await _shop(session, "pp_d")
    product = await _product(session, "Глушитель Невидимка Сайлент")
    await _offer(session, shop, product.id, Decimal(2000), in_stock=False)  # не в наличии

    resp = await client.get("/api/products/search", params={"q": "Невидимка"})
    assert _row(resp.json()["items"], product.id) is None  # нечего сравнивать


async def test_search_min_length(client: AsyncClient) -> None:
    resp = await client.get("/api/products/search", params={"q": "a"})
    assert resp.status_code == 422


# --- Карточка сравнения цен -------------------------------------------------


async def test_product_card_sorts_by_price(client: AsyncClient, session: AsyncSession) -> None:
    a = await _shop(session, "pp_e1")
    b = await _shop(session, "pp_e2")
    product = await _product(session, "gun-compare")
    await _offer(session, a, product.id, Decimal(8000))
    await _offer(session, b, product.id, Decimal(6000))  # дешевле

    resp = await client.get(f"/api/products/{product.slug}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["shops_count"] == 2
    assert Decimal(data["price_min"]) == Decimal(6000)
    assert Decimal(data["price_max"]) == Decimal(8000)
    # дешёвый оффер — первым
    assert Decimal(data["offers"][0]["price"]) == Decimal(6000)


async def test_product_card_out_of_stock_last(client: AsyncClient, session: AsyncSession) -> None:
    a = await _shop(session, "pp_f1")
    b = await _shop(session, "pp_f2")
    product = await _product(session, "mask-stock")
    await _offer(session, a, product.id, Decimal(3000), in_stock=False)  # нет в наличии
    await _offer(session, b, product.id, Decimal(4000))  # в наличии, но дороже

    data = (await client.get(f"/api/products/{product.slug}")).json()
    # в наличии — сначала, несмотря на бо́льшую цену; счётчик магазинов — только доступные
    assert data["offers"][0]["in_stock"] is True
    assert data["offers"][-1]["in_stock"] is False
    assert data["shops_count"] == 1
    assert Decimal(data["price_min"]) == Decimal(4000)


async def test_product_card_404(client: AsyncClient) -> None:
    resp = await client.get("/api/products/nope-does-not-exist")
    assert resp.status_code == 404
