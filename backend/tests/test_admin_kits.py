"""API-тесты админки китов и каталога (httpx.AsyncClient поверх приложения)."""

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import Category, Offer, Product, Shop


async def _shop(session: AsyncSession) -> int:
    shop = Shop(code="admin_shop", name="Admin Shop", base_url="https://a.test")
    session.add(shop)
    await session.flush()
    return shop.id


async def _product(session: AsyncSession, name: str, category_id: int | None = None) -> Product:
    product = Product(name=name, slug=name, match_key=name, category_id=category_id)
    session.add(product)
    await session.flush()
    return product


async def _offer(
    session: AsyncSession, shop_id: int, price: Decimal, product_id: int | None = None
) -> Offer:
    offer = Offer(
        shop_id=shop_id,
        product_id=product_id,
        external_id=f"ext-{price}-{product_id}",
        url="https://a.test/p",
        raw_title="Товар",
        price=price,
        in_stock=True,
        is_active=True,
    )
    session.add(offer)
    await session.flush()
    return offer


async def _category(session: AsyncSession, slug: str) -> int:
    existing = await session.scalar(select(Category.id).where(Category.slug == slug))
    if existing is not None:
        return existing
    cat = Category(slug=slug, name=slug)
    session.add(cat)
    await session.flush()
    return cat.id


async def test_admin_endpoints_require_auth(client: AsyncClient) -> None:
    # Без логина админские роуты закрыты
    assert (await client.get("/api/admin/kits")).status_code == 401
    assert (await client.get("/api/admin/products")).status_code == 401


async def test_create_kit_and_add_fixed_item(
    admin_client: AsyncClient, session: AsyncSession
) -> None:
    shop = await _shop(session)
    product = await _product(session, "Очки защитные")
    await _offer(session, shop, Decimal(1000), product_id=product.id)

    created = await admin_client.post(
        "/api/admin/kits", json={"name": "Стартовый штурмовик", "role": "assault"}
    )
    assert created.status_code == 201
    kit = created.json()
    assert kit["slug"]  # slug сгенерирован
    assert kit["status"] == "draft"

    added = await admin_client.post(
        f"/api/admin/kits/{kit['id']}/items",
        json={"item_type": "fixed", "title": "Очки", "product_id": product.id},
    )
    assert added.status_code == 201
    body = added.json()
    assert len(body["items"]) == 1
    assert body["pricing"]["complete"] is True
    assert float(body["pricing"]["price_min"]) == 1000.0
    assert float(body["pricing"]["price_max"]) == 1000.0


async def test_publish_incomplete_kit_returns_409(
    admin_client: AsyncClient, session: AsyncSession
) -> None:
    product = await _product(session, "Без офферов")  # нет активных офферов
    created = await admin_client.post("/api/admin/kits", json={"name": "Неполный кит"})
    kit_id = created.json()["id"]
    await admin_client.post(
        f"/api/admin/kits/{kit_id}/items",
        json={"item_type": "fixed", "title": "Товар", "product_id": product.id},
    )

    resp = await admin_client.post(f"/api/admin/kits/{kit_id}/publish")
    assert resp.status_code == 409


async def test_flexible_preview_lists_variants(
    admin_client: AsyncClient, session: AsyncSession
) -> None:
    shop = await _shop(session)
    cat = await _category(session, "admin_flex_preview")
    cheap = await _product(session, "Шар дешёвый", cat)
    pricey = await _product(session, "Шар дорогой", cat)
    await _offer(session, shop, Decimal(200), product_id=cheap.id)
    await _offer(session, shop, Decimal(500), product_id=pricey.id)

    created = await admin_client.post("/api/admin/kits", json={"name": "Кит с шарами"})
    kit_id = created.json()["id"]
    item = (
        await admin_client.post(
            f"/api/admin/kits/{kit_id}/items",
            json={"item_type": "flexible", "title": "Шары", "category_id": cat},
        )
    ).json()
    item_id = item["items"][0]["id"]

    preview = await admin_client.get(f"/api/admin/kit-items/{item_id}/preview")
    assert preview.status_code == 200
    variants = preview.json()["variants"]
    assert len(variants) == 2
    assert float(variants[0]["min_price"]) == 200.0  # отсортировано по возрастанию цены


async def test_products_autocomplete(admin_client: AsyncClient, session: AsyncSession) -> None:
    await _product(session, "Привод CYMA CM.028")
    await _product(session, "Маска сетчатая")

    resp = await admin_client.get("/api/admin/products", params={"q": "cyma"})
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()]
    assert any("CYMA" in n for n in names)
    assert all("Маска" not in n for n in names)


async def test_offers_unmatched_and_link(
    admin_client: AsyncClient, session: AsyncSession
) -> None:
    shop = await _shop(session)
    offer = await _offer(session, shop, Decimal(750), product_id=None)  # несматчен
    product = await _product(session, "Целевой товар")

    unmatched = await admin_client.get("/api/admin/offers", params={"status": "unmatched"})
    assert unmatched.status_code == 200
    assert any(o["id"] == offer.id for o in unmatched.json())

    linked = await admin_client.post(
        f"/api/admin/offers/{offer.id}/link", json={"product_id": product.id}
    )
    assert linked.status_code == 200
    assert linked.json()["product_id"] == product.id

    # После привязки оффер больше не среди несматченных
    after = await admin_client.get("/api/admin/offers", params={"status": "unmatched"})
    assert all(o["id"] != offer.id for o in after.json())


@pytest.mark.parametrize("bad_body", [
    {"item_type": "fixed", "title": "нет продукта"},  # fixed без product_id
    {"item_type": "flexible", "title": "нет категории"},  # flexible без category_id
])
async def test_add_item_validation(
    admin_client: AsyncClient, bad_body: dict[str, str]
) -> None:
    kit_id = (await admin_client.post("/api/admin/kits", json={"name": "Валидация"})).json()["id"]
    resp = await admin_client.post(f"/api/admin/kits/{kit_id}/items", json=bad_body)
    assert resp.status_code == 422  # pydantic-валидация тела


async def test_fixed_item_shows_selected_product(
    admin_client: AsyncClient, session: AsyncSession
) -> None:
    shop = await _shop(session)
    product = await _product(session, "Очки ESS")
    await _offer(session, shop, Decimal(1000), product_id=product.id)
    created = await admin_client.post("/api/admin/kits", json={"name": "Показ товара"})
    kit_id = created.json()["id"]
    body = (
        await admin_client.post(
            f"/api/admin/kits/{kit_id}/items",
            json={"item_type": "fixed", "title": "Очки", "product_id": product.id},
        )
    ).json()
    assert body["items"][0]["product"]["name"] == "Очки ESS"


async def test_flexible_curation_pin_and_exclude(
    admin_client: AsyncClient, session: AsyncSession
) -> None:
    shop = await _shop(session)
    cat = await _category(session, "cur_cat")
    p1 = await _product(session, "Шар в категории", cat)
    p2 = await _product(session, "Шар вне категории")  # другая категория
    await _offer(session, shop, Decimal(200), product_id=p1.id)
    await _offer(session, shop, Decimal(300), product_id=p2.id)

    kit_id = (await admin_client.post("/api/admin/kits", json={"name": "Курация"})).json()["id"]
    item = (
        await admin_client.post(
            f"/api/admin/kits/{kit_id}/items",
            json={"item_type": "flexible", "title": "Шары", "category_id": cat},
        )
    ).json()["items"][0]
    item_id = item["id"]

    def variant_ids(resp_json: dict) -> set[int]:
        return {v["product_id"] for v in resp_json["variants"]}

    base = await admin_client.get(f"/api/admin/kit-items/{item_id}/preview")
    assert variant_ids(base.json()) == {p1.id}  # по критериям только p1

    # Закрепляем p2 (вне категории) — попадает в варианты
    pin = await admin_client.put(
        f"/api/admin/kit-items/{item_id}/candidates",
        json={"product_id": p2.id, "is_pinned": True},
    )
    assert pin.status_code == 200
    after_pin = await admin_client.get(f"/api/admin/kit-items/{item_id}/preview")
    assert variant_ids(after_pin.json()) == {p1.id, p2.id}

    # Исключаем p1 — уходит из вариантов
    await admin_client.put(
        f"/api/admin/kit-items/{item_id}/candidates",
        json={"product_id": p1.id, "is_excluded": True},
    )
    after_excl = await admin_client.get(f"/api/admin/kit-items/{item_id}/preview")
    assert variant_ids(after_excl.json()) == {p2.id}

    candidates = (await admin_client.get(f"/api/admin/kit-items/{item_id}/candidates")).json()
    assert len(candidates) == 2

    # Сброс курации p1 (оба флага false) удаляет запись → p1 снова в вариантах
    await admin_client.put(
        f"/api/admin/kit-items/{item_id}/candidates",
        json={"product_id": p1.id, "is_pinned": False, "is_excluded": False},
    )
    reset = (await admin_client.get(f"/api/admin/kit-items/{item_id}/candidates")).json()
    assert len(reset) == 1  # осталась только закреплённая p2
    final = await admin_client.get(f"/api/admin/kit-items/{item_id}/preview")
    assert variant_ids(final.json()) == {p1.id, p2.id}
