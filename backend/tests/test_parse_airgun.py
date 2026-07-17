"""Тест извлечения предложений air-gun.ru на сохранённой HTML-фикстуре."""

from pathlib import Path

from app.parsers.shops.airgun import AirgunParser, parse_listing

FIXTURE = Path(__file__).parent / "fixtures" / "airgun" / "listing.html"


def test_parse_listing_extracts_offers() -> None:
    html = FIXTURE.read_text(encoding="utf-8")
    offers = parse_listing(html, AirgunParser.base_url)

    assert len(offers) == 21  # столько карточек div.product на фикстуре

    first = offers[0]
    assert first.external_id.isdigit()  # числовой element-id из data-id
    assert first.title
    assert first.url.startswith("https://www.air-gun.ru/")
    assert first.image_url and first.image_url.startswith("https://www.air-gun.ru/")


def test_parse_listing_stock_detection() -> None:
    html = FIXTURE.read_text(encoding="utf-8")
    offers = parse_listing(html, AirgunParser.base_url)
    flags = {o.in_stock for o in offers}
    assert flags == {True, False}  # на фикстуре есть «В наличии» и «Под заказ»


def test_parse_listing_price_optional() -> None:
    html = FIXTURE.read_text(encoding="utf-8")
    offers = parse_listing(html, AirgunParser.base_url)
    # часть карточек — «Подробнее» без цены (price=None), часть — с ценой
    prices = [o.price for o in offers]
    assert any(p is not None for p in prices)  # цены распарсены
    assert any(p is None for p in prices)  # и есть карточки без цены


def test_parse_listing_unique_ids() -> None:
    html = FIXTURE.read_text(encoding="utf-8")
    offers = parse_listing(html, AirgunParser.base_url)
    ids = [o.external_id for o in offers]
    assert len(ids) == len(set(ids))
