"""Конвейер приёма данных парсера: upsert офферов, история цен, деактивация.

Ключевые инварианты:
- идемпотентность: повтор прогона с теми же данными не плодит дублей и записей истории;
- история цен пишется только при изменении цены/наличия;
- парсер не может молча уничтожить данные: при аномально малом объёме прогон помечается
  FAILED и деактивация не выполняется (защита от смены вёрстки сайта).
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import Offer, ParseProgress, PriceHistory, Shop
from app.parsers.base import ParsedOffer, Section, ShopParser

log = logging.getLogger("app.ingest")

# Порог предохранителя: если распарсено меньше этой доли от прежнего числа
# активных офферов — считаем прогон сломанным и не деактивируем офферы.
SAFETY_RATIO = 0.5

# Каждые столько офферов писать heartbeat-лог (видно, что прогон жив)
_HEARTBEAT_EVERY = 200

# Лимиты строковых колонок офферов (см. models/catalog.py)
_MAX_TITLE = 512
_MAX_CATEGORY = 512
_MAX_URL = 1024


def _clamp_lengths(parsed: ParsedOffer) -> None:
    """Обрезает строковые поля до лимитов колонок БД (защитно, для всех магазинов)."""
    parsed.title = parsed.title[:_MAX_TITLE]
    parsed.url = parsed.url[:_MAX_URL]
    if parsed.raw_category is not None:
        parsed.raw_category = parsed.raw_category[:_MAX_CATEGORY]
    if parsed.image_url is not None:
        parsed.image_url = parsed.image_url[:_MAX_URL]


@dataclass(slots=True)
class IngestReport:
    """Итоговая сводка прогона парсера."""

    shop_code: str
    total_parsed: int = 0
    created: int = 0
    updated: int = 0
    price_changes: int = 0
    reactivated: int = 0
    deactivated: int = 0
    status: str = "ok"  # ok | failed
    message: str = ""
    errors: list[str] = field(default_factory=list)


async def _get_or_create_shop(session: AsyncSession, parser: ShopParser) -> Shop:
    """Находит магазин по коду или создаёт его (auto-upsert по code)."""
    shop = await session.scalar(select(Shop).where(Shop.code == parser.code))
    if shop is None:
        shop = Shop(code=parser.code, name=parser.name, base_url=parser.base_url)
        session.add(shop)
        await session.flush()
    else:
        shop.name = parser.name
        shop.base_url = parser.base_url
    return shop


async def ingest_shop(
    session: AsyncSession,
    parser: ShopParser,
    safety_ratio: float = SAFETY_RATIO,
    limit: int | None = None,
) -> IngestReport:
    """Прогоняет парсер магазина и синхронизирует офферы в БД.

    `limit` ограничивает число обрабатываемых офферов (для smoke-прогонов и как
    защитный кап). При досрочной остановке по лимиту деактивация не выполняется —
    прогон считается частичным, чтобы не потерять «неувиденные» офферы.
    """
    report = IngestReport(shop_code=parser.code)
    shop = await _get_or_create_shop(session, parser)

    existing: dict[str, Offer] = {
        offer.external_id: offer
        for offer in await session.scalars(select(Offer).where(Offer.shop_id == shop.id))
    }
    prev_active = sum(1 for o in existing.values() if o.is_active)

    # Прогресс/возобновление ведём только для полных прогонов (не smoke с --limit).
    progress: ParseProgress | None = None
    done_sections: frozenset[str] = frozenset()
    run_started_at = datetime.now(UTC)
    if limit is None:
        progress = await _load_or_reset_progress(session, parser.code)
        run_started_at = progress.run_started_at  # тот же ts для деактивации по всему прогону
        if progress.done_sections:  # возобновление прерванного прогона
            done_sections = frozenset(progress.done_sections)
            report.total_parsed = progress.parsed_count  # накоплено за прошлые сегменты
            log.info(
                "[%s] возобновление: пропускаю %d разделов, уже обработано %d офферов",
                parser.code,
                len(done_sections),
                progress.parsed_count,
            )

    log.info("[%s] старт (активных офферов ранее: %d)", parser.code, prev_active)
    partial = False

    async for item in parser.iter_offers(done_sections):
        if isinstance(item, Section):
            if progress is not None:
                progress.done_sections = [*progress.done_sections, item.id]
                progress.parsed_count = report.total_parsed
                await session.commit()  # чекпоинт: раздел зафиксирован в БД
                log.info(
                    "[%s] раздел готов: %s (всего офферов: %d)",
                    parser.code,
                    item.id,
                    report.total_parsed,
                )
            continue

        if limit is not None and report.total_parsed >= limit:
            partial = True
            break
        report.total_parsed += 1
        await _apply_offer(session, shop.id, existing, item, run_started_at, report)
        if report.total_parsed % _HEARTBEAT_EVERY == 0:
            if progress is not None:
                progress.parsed_count = report.total_parsed
            await session.commit()  # частый коммит: прогресс не теряется при обрыве
            log.info(
                "[%s] обработано %d офферов (раздел: %s)",
                parser.code,
                report.total_parsed,
                item.raw_category,
            )

    await session.flush()

    if partial:
        report.message = f"частичный прогон (limit={limit}) — деактивация пропущена"
        await session.commit()
        log.info("[%s] частичный прогон: %d офферов", parser.code, report.total_parsed)
        return report

    if _looks_broken(report.total_parsed, prev_active, safety_ratio):
        report.status = "failed"
        report.message = (
            f"Распарсено {report.total_parsed} при {prev_active} активных ранее — "
            f"ниже порога {safety_ratio:.0%}; деактивация пропущена"
        )
        if progress is not None:
            progress.completed = True  # прогон окончен (все разделы), просто без деактивации
        await session.commit()
        log.warning("[%s] прогон помечен FAILED: %s", parser.code, report.message)
        return report

    result = await session.execute(
        update(Offer)
        .where(
            Offer.shop_id == shop.id,
            Offer.is_active.is_(True),
            Offer.last_seen_at < run_started_at,
        )
        .values(is_active=False)
    )
    report.deactivated = result.rowcount or 0
    if progress is not None:
        progress.completed = True
        progress.parsed_count = report.total_parsed
    await session.commit()
    log.info(
        "[%s] готово: %s (офферов %d, деактивировано %d)",
        parser.code,
        report.status,
        report.total_parsed,
        report.deactivated,
    )
    return report


async def _load_or_reset_progress(session: AsyncSession, shop_code: str) -> ParseProgress:
    """Загружает прогресс магазина; завершённый/отсутствующий — сбрасывает в новый прогон."""
    progress = await session.scalar(
        select(ParseProgress).where(ParseProgress.shop_code == shop_code)
    )
    now = datetime.now(UTC)
    if progress is None:
        progress = ParseProgress(
            shop_code=shop_code,
            run_started_at=now,
            done_sections=[],
            parsed_count=0,
            completed=False,
        )
        session.add(progress)
        await session.flush()
    elif progress.completed:  # прошлый прогон завершён — начинаем с нуля
        progress.run_started_at = now
        progress.done_sections = []
        progress.parsed_count = 0
        progress.completed = False
        await session.flush()
    return progress


async def _apply_offer(
    session: AsyncSession,
    shop_id: int,
    existing: dict[str, Offer],
    parsed: ParsedOffer,
    run_started_at: datetime,
    report: IngestReport,
) -> None:
    """Upsert одного оффера + запись истории цен при изменении цены/наличия."""
    _clamp_lengths(parsed)  # защита от переполнения строковых колонок
    offer = existing.get(parsed.external_id)
    if offer is None:
        offer = Offer(
            shop_id=shop_id,
            external_id=parsed.external_id,
            url=parsed.url,
            raw_title=parsed.title,
            raw_category=parsed.raw_category,
            price=parsed.price,
            in_stock=parsed.in_stock,
            image_url=parsed.image_url,
            is_active=True,
            first_seen_at=run_started_at,
            last_seen_at=run_started_at,
        )
        session.add(offer)
        await session.flush()  # нужен offer.id для записи истории
        existing[parsed.external_id] = offer
        session.add(_history_row(offer, run_started_at))
        report.created += 1
        return

    price_changed = offer.price != parsed.price or offer.in_stock != parsed.in_stock
    if not offer.is_active:
        report.reactivated += 1
    offer.url = parsed.url
    offer.raw_title = parsed.title
    offer.raw_category = parsed.raw_category
    offer.price = parsed.price
    offer.in_stock = parsed.in_stock
    offer.image_url = parsed.image_url
    offer.is_active = True
    offer.last_seen_at = run_started_at
    report.updated += 1
    if price_changed:
        session.add(_history_row(offer, run_started_at))
        report.price_changes += 1


def _history_row(offer: Offer, recorded_at: datetime) -> PriceHistory:
    return PriceHistory(
        offer_id=offer.id,
        price=offer.price,
        in_stock=offer.in_stock,
        recorded_at=recorded_at,
    )


def _looks_broken(parsed: int, prev_active: int, safety_ratio: float) -> bool:
    """True, если объём прогона подозрительно мал (вероятно, сломалась вёрстка)."""
    if parsed == 0 and prev_active > 0:
        return True
    return prev_active > 0 and parsed < prev_active * safety_ratio
