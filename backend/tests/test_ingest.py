"""Тесты ingest-конвейера: идемпотентность, история цен, деактивация, предохранитель."""

from collections.abc import AsyncIterator
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import Offer, PriceHistory, Shop
from app.parsers.base import ParsedOffer, ShopParser
from app.services.ingest import ingest_shop


class FakeParser(ShopParser):
    """Парсер-заглушка: отдаёт заранее заданный список офферов, без сети."""

    code = "test_shop"
    name = "Test Shop"
    base_url = "https://test.local"

    def __init__(self, offers: list[ParsedOffer]) -> None:
        self._offers = offers

    async def iter_offers(
        self, done_sections: frozenset[str] = frozenset()
    ) -> AsyncIterator[ParsedOffer]:
        for offer in self._offers:
            yield offer


def _offer(ext_id: str, price: int, in_stock: bool = True) -> ParsedOffer:
    return ParsedOffer(
        external_id=ext_id,
        url=f"https://test.local/p/{ext_id}",
        title=f"Товар {ext_id}",
        price=Decimal(price),
        in_stock=in_stock,
    )


async def _count(session: AsyncSession, model: type, **filters: object) -> int:
    stmt = select(func.count()).select_from(model)
    for attr, value in filters.items():
        stmt = stmt.where(getattr(model, attr) == value)
    return await session.scalar(stmt) or 0


async def _shop_id(session: AsyncSession) -> int:
    return await session.scalar(select(Shop.id).where(Shop.code == FakeParser.code))


async def _history_count(session: AsyncSession) -> int:
    """Число записей истории цен, ограниченное офферами тестового магазина."""
    shop_id = await _shop_id(session)
    stmt = (
        select(func.count())
        .select_from(PriceHistory)
        .join(Offer, Offer.id == PriceHistory.offer_id)
        .where(Offer.shop_id == shop_id)
    )
    return await session.scalar(stmt) or 0


async def test_ingest_creates_offers_and_history(session: AsyncSession) -> None:
    report = await ingest_shop(session, FakeParser([_offer("1", 100), _offer("2", 200)]))

    assert report.status == "ok"
    assert (report.total_parsed, report.created, report.updated) == (2, 2, 0)

    shop_id = await _shop_id(session)
    assert await _count(session, Offer, shop_id=shop_id) == 2
    # Первичная запись истории на каждый новый оффер
    assert await _history_count(session) == 2


async def test_ingest_is_idempotent(session: AsyncSession) -> None:
    offers = [_offer("1", 100), _offer("2", 200)]
    await ingest_shop(session, FakeParser(offers))
    report = await ingest_shop(session, FakeParser(offers))

    assert (report.created, report.updated, report.price_changes) == (0, 2, 0)
    # Повтор без изменений не добавляет записей истории
    assert await _history_count(session) == 2


async def test_price_change_records_history(session: AsyncSession) -> None:
    await ingest_shop(session, FakeParser([_offer("1", 100)]))
    report = await ingest_shop(session, FakeParser([_offer("1", 150)]))

    assert report.price_changes == 1
    assert await _history_count(session) == 2  # исходная + после изменения

    shop_id = await _shop_id(session)
    offer = await session.scalar(select(Offer).where(Offer.shop_id == shop_id))
    assert offer.price == Decimal(150)


async def test_missing_offer_is_deactivated(session: AsyncSession) -> None:
    # safety_ratio=0 отключает предохранитель, чтобы проверить чистую деактивацию
    await ingest_shop(
        session,
        FakeParser([_offer("1", 100), _offer("2", 200), _offer("3", 300), _offer("4", 400)]),
        safety_ratio=0.0,
    )
    report = await ingest_shop(
        session,
        FakeParser([_offer("1", 100), _offer("2", 200), _offer("3", 300)]),
        safety_ratio=0.0,
    )

    assert report.deactivated == 1
    shop_id = await _shop_id(session)
    assert await _count(session, Offer, shop_id=shop_id, is_active=True) == 3


async def test_safety_threshold_skips_deactivation(session: AsyncSession) -> None:
    await ingest_shop(
        session,
        FakeParser([_offer("1", 100), _offer("2", 200), _offer("3", 300), _offer("4", 400)]),
    )
    # Резкое падение объёма (1 из 4) — прогон считается сломанным
    report = await ingest_shop(session, FakeParser([_offer("1", 100)]))

    assert report.status == "failed"
    assert report.deactivated == 0
    shop_id = await _shop_id(session)
    # Ни один оффер не деактивирован — данные не потеряны
    assert await _count(session, Offer, shop_id=shop_id, is_active=True) == 4
