"""Тест извлечения предложений zorg.pro на сохранённой HTML-фикстуре."""

from decimal import Decimal
from pathlib import Path

from app.parsers.shops.zorg import ZorgParser, parse_categories, parse_listing

FIXTURE = Path(__file__).parent / "fixtures" / "zorg" / "listing.html"
MENU_FIXTURE = Path(__file__).parent / "fixtures" / "zorg" / "catalog_menu.html"


def test_parse_categories_top_level_from_menu() -> None:
    html = MENU_FIXTURE.read_text(encoding="utf-8")
    cats = parse_categories(html, ZorgParser.base_url)

    # только 19 топ-разделов меню (родители агрегируют товары потомков)
    assert len(cats) == 19
    assert len(cats) == len(set(cats))  # без дублей
    # все — одного сегмента /catalog/<slug>/, без фильтров/query
    assert all(c.startswith("https://zorg.pro/catalog/") for c in cats)
    assert not any("/filter/" in c or "?" in c for c in cats)
    assert "https://zorg.pro/catalog/straykbolnoe_oruzhie/" in cats


def test_parse_categories_empty_html() -> None:
    assert parse_categories("<html><body>нет меню</body></html>", ZorgParser.base_url) == []


def test_parse_listing_extracts_offers() -> None:
    html = FIXTURE.read_text(encoding="utf-8")
    offers = parse_listing(html, ZorgParser.base_url)

    assert len(offers) == 23  # столько карточек .catalog_item на фикстуре

    first = offers[0]
    assert first.external_id.isdigit()  # Bitrix-ID из id контейнера
    assert first.title
    assert first.url.startswith("https://zorg.pro/catalog/")
    assert first.price == Decimal("949.05")  # цена с копейками распарсена верно
    assert first.image_url and first.image_url.startswith("https://zorg.pro/")


def test_parse_listing_stock_detection() -> None:
    html = FIXTURE.read_text(encoding="utf-8")
    offers = parse_listing(html, ZorgParser.base_url)
    flags = {o.in_stock for o in offers}
    assert flags == {True, False}  # на фикстуре есть «В наличии» и «Под заказ»


def test_parse_listing_unique_ids() -> None:
    html = FIXTURE.read_text(encoding="utf-8")
    offers = parse_listing(html, ZorgParser.base_url)
    ids = [o.external_id for o in offers]
    assert len(ids) == len(set(ids))
