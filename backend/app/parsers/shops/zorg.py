"""Парсер магазина zorg.pro (1C-Bitrix, статичный рендер каталога).

Каталог плоский: категории — `/catalog/<slug>/`, товары — `/catalog/<cat>/<product>/`.
`parse_listing` — чистая функция извлечения (тестируется на фикстуре);
`iter_offers` — собирает список категорий и обходит их с пагинацией.
"""

import asyncio
import re
from collections.abc import AsyncIterator
from typing import ClassVar
from urllib.parse import urljoin

import httpx
from selectolax.parser import HTMLParser

from app.parsers.base import ParsedOffer, ShopParser, parse_price

# Селекторы карточки товара — при смене вёрстки чинить здесь
_CARD = ".catalog_item"
_TITLE = ".item-title"
_LINK = "a.thumb"
_PRICE_BLOCK = ".price"  # текущая цена; блок старой цены имеет класс .discount
_PRICE_VALUE = ".price_value"
_STOCK = ".item-stock"
_IMAGE = "img.lazy"

# Ссылки категорий верхнего уровня: /catalog/<slug>/ (один сегмент)
_CATEGORY_RE = re.compile(r"^/catalog/[^/]+/$")


def _card_price(card: object) -> str | None:
    """Текущая цена карточки (блок .price без класса .discount)."""
    for block in card.css(_PRICE_BLOCK):  # type: ignore[attr-defined]
        if "discount" in (block.attributes.get("class") or ""):
            continue
        value = block.css_first(_PRICE_VALUE)
        if value:
            return value.text()
    return None


def parse_listing(html: str, base_url: str) -> list[ParsedOffer]:
    """Извлекает предложения со страницы категории zorg.pro."""
    tree = HTMLParser(html)
    breadcrumb = _breadcrumb(tree)
    offers: list[ParsedOffer] = []
    for card in tree.css(_CARD):
        external_id = _external_id(card.attributes.get("id"))
        link = card.css_first(_LINK)
        title = card.css_first(_TITLE)
        if not external_id or link is None or title is None:
            continue
        stock = card.css_first(_STOCK)
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
                in_stock=_is_in_stock(stock.text() if stock else None),
                raw_category=breadcrumb,
                image_url=urljoin(base_url, image_src) if image_src else None,
            )
        )
    return offers


def _external_id(dom_id: str | None) -> str | None:
    """ID товара — хвостовое число Bitrix-идентификатора контейнера (bx_..._NNNNN)."""
    if not dom_id:
        return None
    tail = dom_id.rsplit("_", 1)[-1]
    return tail if tail.isdigit() else None


def _is_in_stock(text: str | None) -> bool:
    """Наличие по тексту .item-stock («В наличии» = да; «Под заказ»/«Нет» = нет)."""
    return bool(text) and "налич" in text.lower()


def _breadcrumb(tree: HTMLParser) -> str | None:
    """Название текущей категории — последняя (самая глубокая) крошка BreadcrumbList."""
    crumbs = tree.css("[itemprop=itemListElement] [itemprop=name]")
    if not crumbs:
        return None
    return (crumbs[-1].text() or "").strip() or None


class ZorgParser(ShopParser):
    code: ClassVar[str] = "zorg"
    name: ClassVar[str] = "Zorg"
    base_url: ClassVar[str] = "https://zorg.pro"

    catalog_root: ClassVar[str] = "https://zorg.pro/catalog/"
    user_agent: ClassVar[str] = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) airsoft_kitfinder-bot"
    )
    request_delay: ClassVar[float] = 0.7
    max_pages_per_category: ClassVar[int] = 50

    async def iter_offers(self) -> AsyncIterator[ParsedOffer]:
        """Собирает категории с индекса каталога и обходит их с пагинацией."""
        headers = {"User-Agent": self.user_agent}
        seen_offer_ids: set[str] = set()
        async with httpx.AsyncClient(
            headers=headers, timeout=20.0, follow_redirects=True
        ) as client:
            root_html = await self._fetch(client, self.catalog_root)
            if root_html is None:
                return
            for category_url in self._category_urls(root_html):
                async for offer in self._iter_category(client, category_url):
                    if offer.external_id not in seen_offer_ids:
                        seen_offer_ids.add(offer.external_id)
                        yield offer

    def _category_urls(self, html: str) -> list[str]:
        """Ссылки категорий верхнего уровня с индекса каталога (дедуп, порядок сохранён)."""
        tree = HTMLParser(html)
        result: list[str] = []
        seen: set[str] = set()
        for anchor in tree.css('a[href^="/catalog/"]'):
            href = anchor.attributes.get("href") or ""
            if _CATEGORY_RE.match(href):
                full = urljoin(self.base_url, href)
                if full not in seen:
                    seen.add(full)
                    result.append(full)
        return result

    async def _iter_category(
        self, client: httpx.AsyncClient, category_url: str
    ) -> AsyncIterator[ParsedOffer]:
        for page in range(1, self.max_pages_per_category + 1):
            url = category_url if page == 1 else f"{category_url}?PAGEN_1={page}"
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
