"""Тесты матчинга: нормализация, слияние офферов между магазинами, идемпотентность."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import Category, Offer, Product, Shop
from app.services.matching import guess_category_slug, match_unmatched, normalize_title


def test_normalize_title_case_and_order() -> None:
    # Регистр и порядок слов не влияют на ключ
    a = normalize_title("Автомат CYMA CM.028")
    b = normalize_title("cyma  автомат   cm 028")
    assert a == b


def test_normalize_title_brand_alias() -> None:
    # «E&L» не рассыпается на токены и совпадает с «el»
    assert "el" in normalize_title("E&L АКС-74").split()


def test_guess_category() -> None:
    assert guess_category_slug("Страйкбольные шары 0.20") == "bbs"
    assert guess_category_slug("Маска сетчатая") == "eyewear"
    assert guess_category_slug("Автомат CYMA CM.028") == "drive"
    assert guess_category_slug("нечто непонятное") is None


async def _make_shop(session: AsyncSession, code: str) -> int:
    shop = Shop(code=code, name=code, base_url=f"https://{code}.test")
    session.add(shop)
    await session.flush()
    return shop.id


async def _add_offer(session: AsyncSession, shop_id: int, ext: str, title: str) -> None:
    session.add(
        Offer(
            shop_id=shop_id, external_id=ext, url=f"https://x/{ext}",
            raw_title=title, price=Decimal(100), in_stock=True, is_active=True,
        )
    )
    await session.flush()


async def test_same_item_across_shops_merges(session: AsyncSession) -> None:
    # Один и тот же товар в двух магазинах с идентичным (после нормализации) названием.
    # Матчим по каждому магазину; поиск по match_key глобальный → сведётся в один товар.
    s1 = await _make_shop(session, "shop_a")
    s2 = await _make_shop(session, "shop_b")
    await _add_offer(session, s1, "1", "Автомат CYMA CM.028")
    await _add_offer(session, s2, "9", "cyma автомат cm 028")

    r1 = await match_unmatched(session, shop_id=s1)
    r2 = await match_unmatched(session, shop_id=s2)

    assert r1.created_products == 1  # первый магазин создал товар
    assert r2.created_products == 0 and r2.linked_existing == 1  # второй привязался к нему

    offers = (await session.scalars(select(Offer).where(Offer.shop_id.in_([s1, s2])))).all()
    product_ids = {o.product_id for o in offers}
    assert len(product_ids) == 1 and None not in product_ids  # оба оффера → один товар


async def test_different_items_stay_separate(session: AsyncSession) -> None:
    s1 = await _make_shop(session, "shop_c")
    await _add_offer(session, s1, "1", "Автомат CYMA CM.028")
    await _add_offer(session, s1, "2", "Пистолет KJW Glock 17")

    report = await match_unmatched(session, shop_id=s1)
    assert report.created_products == 2


async def test_rematch_is_idempotent(session: AsyncSession) -> None:
    s1 = await _make_shop(session, "shop_d")
    await _add_offer(session, s1, "1", "Маска сетчатая чёрная")

    first = await match_unmatched(session, shop_id=s1)
    second = await match_unmatched(session, shop_id=s1)

    assert first.created_products == 1
    # Повтор ничего не обрабатывает: все офферы уже привязаны
    assert second.processed == 0 and second.created_products == 0


async def test_category_assigned(session: AsyncSession) -> None:
    # Гарантируем наличие категории «bbs» независимо от seed
    if await session.scalar(select(Category).where(Category.slug == "bbs")) is None:
        session.add(Category(slug="bbs", name="Шары"))
        await session.flush()

    s1 = await _make_shop(session, "shop_e")
    await _add_offer(session, s1, "1", "Страйкбольные шары 0.25 гр")
    await match_unmatched(session, shop_id=s1)

    offer = await session.scalar(select(Offer).where(Offer.shop_id == s1))
    product = await session.get(Product, offer.product_id)
    assert product.category_id is not None  # категория (bbs) назначена
