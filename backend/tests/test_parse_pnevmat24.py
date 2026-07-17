"""Тест извлечения предложений pnevmat24.ru на сохранённой HTML-фикстуре."""

from pathlib import Path

from app.parsers.shops.pnevmat24 import Pnevmat24Parser, parse_listing

FIXTURE = Path(__file__).parent / "fixtures" / "pnevmat24" / "listing.html"


def test_parse_listing_extracts_offers() -> None:
    html = FIXTURE.read_text(encoding="utf-8")
    offers = parse_listing(html, Pnevmat24Parser.base_url)

    assert len(offers) == 20  # столько карточек .product-card на фикстуре

    first = offers[0]
    assert first.external_id.isdigit()  # OpenCart product_id из data-product-id
    assert first.title
    assert first.url.startswith("https://pnevmat24.ru/")
    assert first.price is not None and first.price > 0
    assert first.image_url and first.image_url.startswith("https://pnevmat24.ru/")


def test_parse_listing_all_in_stock_on_fixture() -> None:
    html = FIXTURE.read_text(encoding="utf-8")
    offers = parse_listing(html, Pnevmat24Parser.base_url)
    # на фикстуре все карточки со статусом «В наличии» (status-available)
    assert all(o.in_stock for o in offers)


def test_parse_listing_unique_ids() -> None:
    html = FIXTURE.read_text(encoding="utf-8")
    offers = parse_listing(html, Pnevmat24Parser.base_url)
    ids = [o.external_id for o in offers]
    assert len(ids) == len(set(ids))


def test_parse_listing_prices_parsed() -> None:
    html = FIXTURE.read_text(encoding="utf-8")
    offers = parse_listing(html, Pnevmat24Parser.base_url)
    # цена извлечена у всех карточек (meta[itemprop=price] на фикстуре есть везде)
    assert all(o.price is not None for o in offers)
