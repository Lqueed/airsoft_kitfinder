"""Тест извлечения предложений airsoftstore.ru на сохранённой HTML-фикстуре.

Фикстура снята через браузер (страница уже за челленджем) — сам парсинг
листинга браузера не требует, тестируется чистая функция parse_listing.
"""

from pathlib import Path

from app.parsers.shops.airsoftstore import AirsoftstoreParser, parse_listing

FIXTURE = Path(__file__).parent / "fixtures" / "airsoftstore" / "listing.html"


def test_parse_listing_extracts_offers() -> None:
    html = FIXTURE.read_text(encoding="utf-8")
    offers = parse_listing(html, AirsoftstoreParser.base_url)

    assert len(offers) == 141  # столько карточек .thumbnail на фикстуре

    first = offers[0]
    assert first.external_id.isdigit()  # VirtueMart product_id из onclick pr_NNNN
    assert first.title
    assert first.url.startswith("https://www.airsoftstore.ru/")
    assert first.price is not None and first.price > 0
    assert first.image_url and "shop_image/product" in first.image_url


def test_parse_listing_stock_detection() -> None:
    html = FIXTURE.read_text(encoding="utf-8")
    offers = parse_listing(html, AirsoftstoreParser.base_url)
    flags = {o.in_stock for o in offers}
    assert flags == {True, False}  # на фикстуре есть «в наличии» и нет


def test_parse_listing_all_have_external_id() -> None:
    html = FIXTURE.read_text(encoding="utf-8")
    offers = parse_listing(html, AirsoftstoreParser.base_url)
    assert all(o.external_id.isdigit() for o in offers)


def test_parse_listing_unique_ids() -> None:
    html = FIXTURE.read_text(encoding="utf-8")
    offers = parse_listing(html, AirsoftstoreParser.base_url)
    ids = [o.external_id for o in offers]
    assert len(ids) == len(set(ids))
