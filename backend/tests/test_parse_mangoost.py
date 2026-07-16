"""Тест извлечения предложений mangoost-airsoft.ru на HTML-фикстуре."""

from decimal import Decimal
from pathlib import Path

from app.parsers.shops.mangoost import MangoostParser, parse_listing

FIXTURE = Path(__file__).parent / "fixtures" / "mangoost" / "listing.html"


def test_parse_listing_extracts_offers() -> None:
    html = FIXTURE.read_text(encoding="utf-8")
    offers = parse_listing(html, MangoostParser.base_url)

    assert len(offers) == 36  # столько карточек form.product_brief_block на фикстуре

    first = offers[0]
    assert first.external_id.isdigit()  # UMI-ID из атрибута rel
    assert first.title
    assert first.url.startswith("https://www.mangoost-airsoft.ru/product/")
    assert first.price == Decimal("10")
    # raw_category берётся из h1 категории
    assert first.raw_category and "страйкбол" in first.raw_category.lower()


def test_parse_listing_unique_ids() -> None:
    html = FIXTURE.read_text(encoding="utf-8")
    offers = parse_listing(html, MangoostParser.base_url)
    ids = [o.external_id for o in offers]
    assert len(ids) == len(set(ids))


def test_parse_listing_images() -> None:
    html = FIXTURE.read_text(encoding="utf-8")
    offers = parse_listing(html, MangoostParser.base_url)
    with_image = [o for o in offers if o.image_url]
    assert with_image  # у большинства карточек есть картинка
    assert all(o.image_url.startswith("https://www.mangoost-airsoft.ru/") for o in with_image)
