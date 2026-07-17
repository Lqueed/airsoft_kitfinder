"""Тест извлечения предложений strikeplanet на сохранённой HTML-фикстуре."""

from decimal import Decimal
from pathlib import Path

from app.parsers.shops.strikeplanet import (
    StrikeplanetParser,
    parse_categories,
    parse_listing,
)

FIXTURE = Path(__file__).parent / "fixtures" / "strikeplanet" / "listing.html"
MENU_FIXTURE = Path(__file__).parent / "fixtures" / "strikeplanet" / "catalog_menu.html"


def test_parse_listing_extracts_offers() -> None:
    html = FIXTURE.read_text(encoding="utf-8")
    offers = parse_listing(html, StrikeplanetParser.base_url)

    assert len(offers) == 9  # столько карточек на странице фикстуры

    first = offers[0]
    assert first.external_id  # Bitrix data-element-id заполнен
    assert first.title
    assert first.url.startswith("https://strikeplanet.ru/catalog/")
    assert first.price is not None and first.price > Decimal(0)

    # На фикстуре есть и товары в наличии, и один без — проверяем оба пути детекции
    in_stock_flags = {o.in_stock for o in offers}
    assert in_stock_flags == {True, False}


def test_parse_listing_unique_external_ids() -> None:
    html = FIXTURE.read_text(encoding="utf-8")
    offers = parse_listing(html, StrikeplanetParser.base_url)
    ids = [o.external_id for o in offers]
    assert len(ids) == len(set(ids))  # ID не дублируются


def test_parse_listing_empty_html() -> None:
    # Пустой/сломанный HTML не роняет парсер, а даёт пустой список
    result = parse_listing("<html><body>нет карточек</body></html>", StrikeplanetParser.base_url)
    assert result == []


def test_parse_categories_from_menu() -> None:
    html = MENU_FIXTURE.read_text(encoding="utf-8")
    cats = parse_categories(html, StrikeplanetParser.base_url)

    # берём только топ-разделы (агрегируют товары потомков), дедуп
    assert len(cats) == 18
    assert len(cats) == len(set(cats))  # без дублей (меню продублировано в DOM)
    assert all(c.startswith("https://strikeplanet.ru/catalog/") for c in cats)
    # фасеточные фильтры и query-срезы отсечены
    assert not any("/filter/" in c or "?" in c for c in cats)
    # профильные разделы на месте
    assert "https://strikeplanet.ru/catalog/straykbolnoe-oruzhie/" in cats


def test_parse_categories_empty_html() -> None:
    assert parse_categories("<html><body>нет меню</body></html>", StrikeplanetParser.base_url) == []
