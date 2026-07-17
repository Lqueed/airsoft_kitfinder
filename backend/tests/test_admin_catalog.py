"""API-тесты каталога магазина: поиск/фильтры офферов, магазины в /api/meta."""

from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import Offer, Product, Shop


async def _shop(session: AsyncSession, code: str) -> int:
    shop = Shop(code=code, name=f"Магазин {code}", base_url=f"https://{code}.test")
    session.add(shop)
    await session.flush()
    return shop.id


async def _offer(
    session: AsyncSession,
    shop_id: int,
    title: str,
    *,
    product_id: int | None = None,
    is_active: bool = True,
) -> Offer:
    offer = Offer(
        shop_id=shop_id,
        product_id=product_id,
        external_id=f"{shop_id}-{title}",
        url="https://x/p",
        raw_title=title,
        price=Decimal(100),
        in_stock=True,
        is_active=is_active,
    )
    session.add(offer)
    await session.flush()
    return offer


async def test_offers_filter_by_shop(admin_client: AsyncClient, session: AsyncSession) -> None:
    a = await _shop(session, "cat_a")
    b = await _shop(session, "cat_b")
    await _offer(session, a, "Шары A")
    await _offer(session, b, "Шары B")

    resp = await admin_client.get("/api/admin/offers", params={"shop": "cat_a"})
    assert resp.status_code == 200
    codes = {o["shop"]["code"] for o in resp.json()}
    assert codes == {"cat_a"}


async def test_offers_search_by_title(admin_client: AsyncClient, session: AsyncSession) -> None:
    shop = await _shop(session, "cat_search")
    await _offer(session, shop, "Шары Exact 0.25")
    await _offer(session, shop, "Маска сетчатая")

    resp = await admin_client.get("/api/admin/offers", params={"shop": "cat_search", "q": "exact"})
    titles = [o["raw_title"] for o in resp.json()]
    assert any("Exact" in t for t in titles)
    assert all("Маска" not in t for t in titles)


async def test_offers_status_filter(admin_client: AsyncClient, session: AsyncSession) -> None:
    shop = await _shop(session, "cat_status")
    product = Product(name="p", slug="p-cat-status", match_key="p-cat-status")
    session.add(product)
    await session.flush()
    await _offer(session, shop, "Сматченный", product_id=product.id)
    await _offer(session, shop, "Несматченный", product_id=None)

    unmatched = await admin_client.get(
        "/api/admin/offers", params={"shop": "cat_status", "status": "unmatched"}
    )
    assert [o["raw_title"] for o in unmatched.json()] == ["Несматченный"]

    matched = await admin_client.get(
        "/api/admin/offers", params={"shop": "cat_status", "status": "matched"}
    )
    assert [o["raw_title"] for o in matched.json()] == ["Сматченный"]


async def test_offers_active_filter(admin_client: AsyncClient, session: AsyncSession) -> None:
    shop = await _shop(session, "cat_active")
    await _offer(session, shop, "Живой", is_active=True)
    await _offer(session, shop, "Снятый", is_active=False)

    only_active = await admin_client.get(
        "/api/admin/offers", params={"shop": "cat_active", "active": "true"}
    )
    assert [o["raw_title"] for o in only_active.json()] == ["Живой"]

    # без фильтра активности — оба
    both = await admin_client.get("/api/admin/offers", params={"shop": "cat_active"})
    assert len(both.json()) == 2


async def test_meta_includes_shops(admin_client: AsyncClient, session: AsyncSession) -> None:
    await _shop(session, "cat_meta")
    resp = await admin_client.get("/api/meta")
    assert resp.status_code == 200
    codes = {s["code"] for s in resp.json()["shops"]}
    assert "cat_meta" in codes
