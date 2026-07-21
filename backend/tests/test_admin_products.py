"""API-тесты админ-управления товарами: список/агрегаты, правка, merge, bulk, офферы.

Тесты идут на реальной БД (с откатом транзакции), которая может быть наполнена —
поэтому проверки основаны на membership своих товаров (уникальные префиксы в имени),
а не на абсолютных числах по всей таблице.
"""

from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import (
    Category,
    Kit,
    KitItem,
    KitItemCandidate,
    Offer,
    Product,
    Shop,
)
from app.models.enums import KitItemType, KitStatus

_UID = "prodtest"  # уникальный маркер тестовых сущностей


async def _shop(session: AsyncSession, code: str) -> int:
    shop = Shop(code=f"{_UID}-{code}", name=f"Магазин {code}", base_url=f"https://{code}.test")
    session.add(shop)
    await session.flush()
    return shop.id


async def _product(
    session: AsyncSession,
    name: str,
    *,
    category_id: int | None = None,
    brand: str | None = None,
) -> Product:
    key = f"{_UID}-{name}"
    product = Product(
        name=name, slug=key, match_key=key, category_id=category_id, brand=brand, attrs={}
    )
    session.add(product)
    await session.flush()
    return product


async def _offer(
    session: AsyncSession,
    shop_id: int,
    title: str,
    *,
    product_id: int | None = None,
    price: Decimal | None = Decimal(100),
    in_stock: bool = True,
    is_active: bool = True,
) -> Offer:
    offer = Offer(
        shop_id=shop_id,
        product_id=product_id,
        external_id=f"{shop_id}-{title}",
        url="https://x/p",
        raw_title=title,
        price=price,
        in_stock=in_stock,
        is_active=is_active,
    )
    session.add(offer)
    await session.flush()
    return offer


async def _category(session: AsyncSession, slug: str) -> int:
    full = f"{_UID}-{slug}"
    existing = await session.scalar(select(Category).where(Category.slug == full))
    if existing is not None:
        return existing.id
    cat = Category(slug=full, name=slug)
    session.add(cat)
    await session.flush()
    return cat.id


async def _kit_with_fixed(session: AsyncSession, product_id: int) -> tuple[int, int]:
    """Кит с fixed-позицией на товар. Возвращает (kit_id, item_id)."""
    kit = Kit(slug=f"{_UID}-kit-{product_id}", name="Тест-кит", status=KitStatus.DRAFT)
    session.add(kit)
    await session.flush()
    item = KitItem(kit_id=kit.id, item_type=KitItemType.FIXED, title="поз", product_id=product_id)
    session.add(item)
    await session.flush()
    return kit.id, item.id


# --- Авторизация -----------------------------------------------------------


async def test_products_require_auth(client: AsyncClient) -> None:
    assert (await client.get("/api/admin/products")).status_code == 401
    assert (await client.get("/api/admin/products/1")).status_code == 401
    assert (await client.patch("/api/admin/products/1", json={})).status_code == 401
    assert (await client.delete("/api/admin/products/1")).status_code == 401
    assert (
        await client.post("/api/admin/products/1/merge", json={"source_ids": [2]})
    ).status_code == 401
    assert (
        await client.post("/api/admin/products/bulk", json={"action": "delete", "product_ids": [1]})
    ).status_code == 401
    assert (await client.post("/api/admin/offers/1/unlink")).status_code == 401
    assert (await client.post("/api/admin/offers/1/create-product")).status_code == 401


# --- Список и агрегаты -----------------------------------------------------


async def test_list_aggregates(admin_client: AsyncClient, session: AsyncSession) -> None:
    p = await _product(session, "ZZ Агрегатный товар")
    s1 = await _shop(session, "agg1")
    s2 = await _shop(session, "agg2")
    await _offer(session, s1, "o1", product_id=p.id, price=Decimal(200), in_stock=True)
    await _offer(session, s2, "o2", product_id=p.id, price=Decimal(150), in_stock=True)
    # снятый оффер с низкой ценой — не должен влиять на счётчики/цену
    await _offer(session, s1, "o3", product_id=p.id, price=Decimal(1), is_active=False)

    resp = await admin_client.get("/api/admin/products", params={"q": "ZZ Агрегатный"})
    assert resp.status_code == 200
    row = next(r for r in resp.json()["items"] if r["id"] == p.id)
    assert row["offers_count"] == 2  # снятый не в счёте
    assert row["shops_count"] == 2
    assert Decimal(row["price_min"]) == Decimal(150)
    assert Decimal(row["price_max"]) == Decimal(200)  # цена только по активным


async def test_list_pagination(admin_client: AsyncClient, session: AsyncSession) -> None:
    for i in range(5):
        await _product(session, f"ZZPag {i:02d}")
    r1 = await admin_client.get(
        "/api/admin/products", params={"q": "ZZPag", "page": 1, "page_size": 2, "sort": "name"}
    )
    body = r1.json()
    assert body["total"] == 5
    assert len(body["items"]) == 2
    assert body["items"][0]["name"] == "ZZPag 00"


async def test_list_filters(admin_client: AsyncClient, session: AsyncSession) -> None:
    cat = await _category(session, "flt")
    with_cat = await _product(session, "ZZFlt с категорией", category_id=cat)
    no_cat = await _product(session, "ZZFlt без категории")
    multishop = await _product(session, "ZZFlt мультимаг")
    s1 = await _shop(session, "flt1")
    s2 = await _shop(session, "flt2")
    await _offer(session, s1, "m1", product_id=multishop.id)
    await _offer(session, s2, "m2", product_id=multishop.id)

    only_no_cat = await admin_client.get(
        "/api/admin/products", params={"q": "ZZFlt", "no_category": "true"}
    )
    ids = {r["id"] for r in only_no_cat.json()["items"]}
    assert no_cat.id in ids and with_cat.id not in ids

    only_cat = await admin_client.get(
        "/api/admin/products", params={"q": "ZZFlt", "category_id": cat}
    )
    assert {r["id"] for r in only_cat.json()["items"]} == {with_cat.id}

    only_multi = await admin_client.get(
        "/api/admin/products", params={"q": "ZZFlt", "multishop": "true"}
    )
    assert {r["id"] for r in only_multi.json()["items"]} == {multishop.id}


async def test_list_sort_price_nulls_last(admin_client: AsyncClient, session: AsyncSession) -> None:
    cheap = await _product(session, "ZZSort дешёвый")
    pricey = await _product(session, "ZZSort дорогой")
    no_price = await _product(session, "ZZSort без цены")
    s = await _shop(session, "sort")
    await _offer(session, s, "c", product_id=cheap.id, price=Decimal(100))
    await _offer(session, s, "d", product_id=pricey.id, price=Decimal(500))

    resp = await admin_client.get(
        "/api/admin/products", params={"q": "ZZSort", "sort": "price_min", "order": "asc"}
    )
    ordered = [r["id"] for r in resp.json()["items"]]
    assert ordered.index(cheap.id) < ordered.index(pricey.id)
    assert ordered[-1] == no_price.id  # без цены — в конце (NULLS LAST)


# --- Карточка и правка -----------------------------------------------------


async def test_detail_includes_inactive_offers(
    admin_client: AsyncClient, session: AsyncSession
) -> None:
    p = await _product(session, "ZZ Деталь")
    s = await _shop(session, "det")
    await _offer(session, s, "живой", product_id=p.id, is_active=True)
    await _offer(session, s, "снятый", product_id=p.id, is_active=False)

    resp = await admin_client.get(f"/api/admin/products/{p.id}")
    assert resp.status_code == 200
    titles = {o["raw_title"] for o in resp.json()["offers"]}
    assert titles == {"живой", "снятый"}  # в детали все офферы


async def test_patch_keeps_match_key_and_slug(
    admin_client: AsyncClient, session: AsyncSession
) -> None:
    cat = await _category(session, "patch")
    p = await _product(session, "ZZ Старое имя")
    old_slug, old_key = p.slug, p.match_key

    resp = await admin_client.patch(
        f"/api/admin/products/{p.id}",
        json={"name": "ZZ Новое имя", "brand": "БрендХ", "category_id": cat},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "ZZ Новое имя"
    assert body["brand"] == "БрендХ"
    assert body["category_id"] == cat
    assert body["slug"] == old_slug  # slug не меняется
    assert body["match_key"] == old_key  # match_key не меняется


async def test_patch_bad_category(admin_client: AsyncClient, session: AsyncSession) -> None:
    p = await _product(session, "ZZ КатегорияBad")
    resp = await admin_client.patch(f"/api/admin/products/{p.id}", json={"category_id": 99999999})
    assert resp.status_code == 404


# --- Удаление --------------------------------------------------------------


async def test_delete_blocked_by_fixed_kit(
    admin_client: AsyncClient, session: AsyncSession
) -> None:
    p = await _product(session, "ZZ ВКите")
    kit_id, _ = await _kit_with_fixed(session, p.id)
    resp = await admin_client.delete(f"/api/admin/products/{p.id}")
    assert resp.status_code == 409
    assert str(kit_id) in resp.json()["detail"]
    assert await session.get(Product, p.id) is not None  # не удалён


async def test_delete_unlinks_offers_and_candidates(
    admin_client: AsyncClient, session: AsyncSession
) -> None:
    p = await _product(session, "ZZ НаУдаление")
    s = await _shop(session, "del")
    offer = await _offer(session, s, "o", product_id=p.id)
    resp = await admin_client.delete(f"/api/admin/products/{p.id}")
    assert resp.status_code == 204
    assert await session.get(Product, p.id) is None
    await session.refresh(offer)
    assert offer.product_id is None  # оффер отвязан, не удалён


# --- Merge -----------------------------------------------------------------


async def test_merge_basic(admin_client: AsyncClient, session: AsyncSession) -> None:
    target = await _product(session, "ZZ Цель")
    src = await _product(session, "ZZ Дубль")
    s = await _shop(session, "merge")
    offer = await _offer(session, s, "o", product_id=src.id)

    resp = await admin_client.post(
        f"/api/admin/products/{target.id}/merge", json={"source_ids": [src.id]}
    )
    assert resp.status_code == 200
    await session.refresh(offer)
    assert offer.product_id == target.id  # оффер перевешен на цель
    assert await session.get(Product, src.id) is None  # дубль удалён


async def test_merge_candidate_conflict(admin_client: AsyncClient, session: AsyncSession) -> None:
    target = await _product(session, "ZZ MCЦель")
    src = await _product(session, "ZZ MCДубль")
    kit_id, item_id = await _kit_with_fixed(session, target.id)
    # у одного kit_item кандидаты и на цель (pinned), и на дубль (excluded)
    session.add(KitItemCandidate(kit_item_id=item_id, product_id=target.id, is_pinned=True))
    session.add(KitItemCandidate(kit_item_id=item_id, product_id=src.id, is_excluded=True))
    await session.flush()

    resp = await admin_client.post(
        f"/api/admin/products/{target.id}/merge", json={"source_ids": [src.id]}
    )
    assert resp.status_code == 200  # без UniqueViolation
    rows = (
        await session.scalars(
            select(KitItemCandidate).where(KitItemCandidate.kit_item_id == item_id)
        )
    ).all()
    assert len(rows) == 1  # одна строка на kit_item
    assert rows[0].product_id == target.id
    assert rows[0].is_pinned and rows[0].is_excluded  # флаги свёрнуты OR


async def test_merge_idempotent_and_self(admin_client: AsyncClient, session: AsyncSession) -> None:
    target = await _product(session, "ZZ Идемп")
    # source = сам target → no-op, товар жив
    r1 = await admin_client.post(
        f"/api/admin/products/{target.id}/merge", json={"source_ids": [target.id]}
    )
    assert r1.status_code == 200
    assert await session.get(Product, target.id) is not None
    # повтор с несуществующим id → no-op
    r2 = await admin_client.post(
        f"/api/admin/products/{target.id}/merge", json={"source_ids": [99999999]}
    )
    assert r2.status_code == 200


# --- Офферы: unlink / create-product ---------------------------------------


async def test_unlink_offer(admin_client: AsyncClient, session: AsyncSession) -> None:
    p = await _product(session, "ZZ Отвязка")
    s = await _shop(session, "unlink")
    offer = await _offer(session, s, "o", product_id=p.id)
    resp = await admin_client.post(f"/api/admin/offers/{offer.id}/unlink")
    assert resp.status_code == 200
    await session.refresh(offer)
    assert offer.product_id is None


async def test_create_product_from_offer(admin_client: AsyncClient, session: AsyncSession) -> None:
    s = await _shop(session, "cpo")
    offer = await _offer(session, s, "ZZ Уникальный несматченный товар 12345", product_id=None)
    resp = await admin_client.post(f"/api/admin/offers/{offer.id}/create-product")
    assert resp.status_code == 200
    body = resp.json()
    assert body["created"] is True
    await session.refresh(offer)
    assert offer.product_id == body["product"]["id"]  # оффер привязан к новому товару


# --- Bulk ------------------------------------------------------------------


async def test_bulk_set_category_and_brand(
    admin_client: AsyncClient, session: AsyncSession
) -> None:
    cat = await _category(session, "bulk")
    p1 = await _product(session, "ZZBulk 1")
    p2 = await _product(session, "ZZBulk 2")

    r_cat = await admin_client.post(
        "/api/admin/products/bulk",
        json={"action": "set_category", "product_ids": [p1.id, p2.id], "category_id": cat},
    )
    assert r_cat.status_code == 200
    assert r_cat.json()["succeeded"] == 2
    for p in (p1, p2):
        await session.refresh(p)
        assert p.category_id == cat

    r_brand = await admin_client.post(
        "/api/admin/products/bulk",
        json={"action": "set_brand", "product_ids": [p1.id], "brand": "МассБренд"},
    )
    assert r_brand.status_code == 200
    await session.refresh(p1)
    assert p1.brand == "МассБренд"


async def test_bulk_delete_partial_failure(
    admin_client: AsyncClient, session: AsyncSession
) -> None:
    ok_product = await _product(session, "ZZBD ok")
    in_kit = await _product(session, "ZZBD вките")
    await _kit_with_fixed(session, in_kit.id)

    resp = await admin_client.post(
        "/api/admin/products/bulk",
        json={"action": "delete", "product_ids": [ok_product.id, in_kit.id]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["succeeded"] == 1
    by_id = {r["product_id"]: r for r in body["results"]}
    assert by_id[ok_product.id]["ok"] is True
    assert by_id[in_kit.id]["ok"] is False and by_id[in_kit.id]["error"]
    # частичная ошибка не откатила успешное удаление
    assert await session.get(Product, ok_product.id) is None
    assert await session.get(Product, in_kit.id) is not None
