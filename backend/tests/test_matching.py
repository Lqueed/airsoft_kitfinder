"""Тесты матчинга: нормализация, слияние офферов между магазинами, идемпотентность."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import Category, Offer, Product, Shop
from app.services.matching import (
    bbs_match_key,
    guess_category_slug,
    match_unmatched,
    normalize_title,
)


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


def test_bbs_key_weight_formats_equal() -> None:
    # Разный формат веса и языка → один ключ (бренд+вес+цвет+тип)
    sp = bbs_match_key("Шары Азот 0.30г. 3333шт.")
    mg = bbs_match_key("Аzot Strike Шары 0,30 гр (белые, 1 кг, пакет)")  # кириллическая А
    assert sp is not None and mg is not None
    assert sp[0] == mg[0] == "bbs:azot|0.3|white|n"


def test_bbs_key_glued_and_no_unit() -> None:
    # Слипшийся токен и вес без единицы измерения всё равно распознаются
    assert bbs_match_key("BLS 14443 bbs0.50g Precision Gray 1000 pcs")[0] == "bbs:bls|0.5|gray|n"
    assert bbs_match_key("Mad Bull 7185 tracer BBS 0.25 green")[0] == "bbs:madbull|0.25|green|t"


def test_bbs_key_color_and_tracer_separate() -> None:
    # Разный цвет и тип трассера не сливаются
    red = bbs_match_key("BLS tracer 0.25g (RED)")[0]
    green = bbs_match_key("BLS Шары трассирующие 0,25 гр (зеленые)")[0]
    plain = bbs_match_key("BLS bbs 0.25 g 4000 pcs")[0]
    assert red == "bbs:bls|0.25|red|t"
    assert green == "bbs:bls|0.25|green|t"
    assert plain == "bbs:bls|0.25|white|n"
    assert len({red, green, plain}) == 3


def test_bbs_key_none_for_non_bbs() -> None:
    # Не шар (лоадер/мишень) или неизвестный бренд → ключ не строится (уйдёт на фолбэк)
    assert bbs_match_key("CYMA Лоадер (470)") is None  # нет веса шара
    assert bbs_match_key("Мишень 14 х 14 см") is None
    assert bbs_match_key("Шары НоунеймБренд 0.20") is None  # неизвестный бренд


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


async def test_bbs_same_ball_merges_across_shops(session: AsyncSession) -> None:
    # Один и тот же шар (BLS 0.30 белый) в трёх магазинах с разным форматом
    # названия сводится в один товар; атрибуты и бренд заполняются структурно.
    s1 = await _make_shop(session, "bbs_sp")
    s2 = await _make_shop(session, "bbs_zorg")
    s3 = await _make_shop(session, "bbs_mangoost")
    await _add_offer(session, s1, "1", "Шары BLS 0.30г. 3333шт.")
    await _add_offer(session, s2, "2", "BLS 14430 bbs 0.30g Precision White 1 kg")
    await _add_offer(session, s3, "3", "BLS Шары 0,30 гр (белые, 3300 шт)")

    await match_unmatched(session, shop_id=s1)
    await match_unmatched(session, shop_id=s2)
    await match_unmatched(session, shop_id=s3)

    offers = (await session.scalars(
        select(Offer).where(Offer.shop_id.in_([s1, s2, s3]))
    )).all()
    product_ids = {o.product_id for o in offers}
    assert len(product_ids) == 1 and None not in product_ids  # три оффера → один товар

    product = await session.get(Product, next(iter(product_ids)))
    assert product.brand == "bls"
    assert product.attrs == {"brand": "bls", "weight": 0.3, "color": "white", "tracer": False}
