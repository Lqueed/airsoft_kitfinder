"""Тест извлечения предложений zorg.pro на сохранённой HTML-фикстуре."""

from decimal import Decimal
from pathlib import Path

from app.parsers.shops.zorg import ZorgParser, parse_listing

FIXTURE = Path(__file__).parent / "fixtures" / "zorg" / "listing.html"


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
