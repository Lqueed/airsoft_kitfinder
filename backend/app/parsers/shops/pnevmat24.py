"""Парсер магазина pnevmat24.ru (OpenCart, статичный рендер каталога).

Пневмо-магазин; парсим ТОЛЬКО раздел снаряжения/экипировки (одежда, обувь,
защита/бронежилеты, разгрузки-плитники, подсумки) — оружие и пневматика лежат
в других разделах и не обходятся. Категории заданы явным списком листьев;
родительская категория показывает товары всего поддерева, поэтому дедуп по
external_id обязателен.

`parse_listing` — чистая функция извлечения (тестируется на фикстуре);
`iter_offers` — обходит целевые категории с постраничной пагинацией `?page=N`.
"""

import asyncio
from collections.abc import AsyncIterator
from typing import ClassVar
from urllib.parse import urljoin

import httpx
from selectolax.parser import HTMLParser

from app.parsers.base import ParsedOffer, ShopParser, parse_price

# Селекторы карточки товара в листинге — при смене вёрстки чинить здесь
_CARD = "div.product-card"
_TITLE = '.product-card__name span[itemprop="name"]'
_LINK = '.product-card__name a[itemprop="url"]'
_PRICE_META = '.product-card__prices meta[itemprop="price"]'  # надёжнее текста
_PRICE_TEXT = ".product-card__price"  # фолбэк
_STOCK = ".product-card__stock-status span"
_IMAGE = '.product-card__image img[itemprop="image"]'
_PRODUCT_ID = "[data-product-id]"  # стабильный OpenCart product_id

# Класс статуса «в наличии» (иначе «Под заказ»/«Снят с продажи» → нет)
_IN_STOCK_CLASS = "status-available"


def _card_price(card: object) -> str | None:
    """Цена карточки: meta[itemprop=price] (число), с фолбэком на текст блока."""
    meta = card.css_first(_PRICE_META)  # type: ignore[attr-defined]
    if meta is not None:
        content = meta.attributes.get("content")
        if content:
            return content
    text = card.css_first(_PRICE_TEXT)  # type: ignore[attr-defined]
    return text.text() if text else None


def _is_in_stock(card: object) -> bool:
    """Наличие по классу span в блоке статуса (status-available = да)."""
    span = card.css_first(_STOCK)  # type: ignore[attr-defined]
    if span is None:
        return False
    return _IN_STOCK_CLASS in (span.attributes.get("class") or "")


def parse_listing(html: str, base_url: str) -> list[ParsedOffer]:
    """Извлекает предложения со страницы категории pnevmat24."""
    tree = HTMLParser(html)
    h1 = tree.css_first("h1")
    category = (h1.text().strip() if h1 else None) or None
    offers: list[ParsedOffer] = []
    for card in tree.css(_CARD):
        id_node = card.css_first(_PRODUCT_ID)
        external_id = id_node.attributes.get("data-product-id") if id_node else None
        link = card.css_first(_LINK)
        title = card.css_first(_TITLE)
        if not external_id or link is None or title is None:
            continue
        image = card.css_first(_IMAGE)
        image_src = None
        if image is not None:
            image_src = image.attributes.get("data-src") or image.attributes.get("src")
        offers.append(
            ParsedOffer(
                external_id=external_id,
                url=urljoin(base_url, link.attributes.get("href") or ""),
                title=title.text().strip(),
                price=parse_price(_card_price(card)),
                in_stock=_is_in_stock(card),
                raw_category=category,
                image_url=urljoin(base_url, image_src) if image_src else None,
            )
        )
    return offers


class Pnevmat24Parser(ShopParser):
    code: ClassVar[str] = "pnevmat24"
    name: ClassVar[str] = "Пневмат24"
    base_url: ClassVar[str] = "https://pnevmat24.ru"

    # Целевые категории снаряжения (листья раздела /snaryazhenie-i-odezhda/).
    # Оружие/пневматика — в других разделах, здесь не обходятся.
    category_paths: ClassVar[tuple[str, ...]] = (
        "/snaryazhenie-i-odezhda/odezhda-dlya-ohoty/",  # тактическая одежда и обувь
        "/snaryazhenie-i-odezhda/zhilety-1/",  # разгрузочные системы (плитники)
        "/snaryazhenie-i-odezhda/zashchita/",  # защитная амуниция (бронежилеты)
        "/snaryazhenie-i-odezhda/podsumki/",  # подсумки
    )
    user_agent: ClassVar[str] = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) airsoft_kitfinder-bot"
    )
    request_delay: ClassVar[float] = 0.7
    max_pages_per_category: ClassVar[int] = 100

    async def iter_offers(self) -> AsyncIterator[ParsedOffer]:
        """Обходит целевые категории снаряжения с пагинацией `?page=N`."""
        headers = {"User-Agent": self.user_agent}
        seen_offer_ids: set[str] = set()
        async with httpx.AsyncClient(
            headers=headers, timeout=25.0, follow_redirects=True
        ) as client:
            for path in self.category_paths:
                category_url = urljoin(self.base_url, path)
                async for offer in self._iter_category(client, category_url):
                    if offer.external_id not in seen_offer_ids:
                        seen_offer_ids.add(offer.external_id)
                        yield offer

    async def _iter_category(
        self, client: httpx.AsyncClient, category_url: str
    ) -> AsyncIterator[ParsedOffer]:
        for page in range(1, self.max_pages_per_category + 1):
            url = category_url if page == 1 else f"{category_url}?page={page}"
            html = await self._fetch(client, url)
            if html is None:
                break
            offers = parse_listing(html, self.base_url)
            if not offers:
                break
            for offer in offers:
                yield offer

    async def _fetch(self, client: httpx.AsyncClient, url: str) -> str | None:
        await asyncio.sleep(self.request_delay)
        try:
            response = await client.get(url)
        except httpx.HTTPError:
            return None
        if response.status_code != 200:
            return None
        return response.text
