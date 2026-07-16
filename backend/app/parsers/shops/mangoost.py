"""Парсер магазина mangoost-airsoft.ru (UMI.CMS, статичный рендер каталога).

Категории — `/category/<slug>/`, товары — `/product/<id|slug>/`. Все товары
категории доступны одной страницей через суффикс `/all/`.
`parse_listing` — чистая функция извлечения (тестируется на фикстуре).
"""

import asyncio
from collections.abc import AsyncIterator
from decimal import Decimal
from typing import ClassVar
from urllib.parse import urljoin

import httpx
from selectolax.parser import HTMLParser

from app.parsers.base import ParsedOffer, ShopParser, parse_price

# Селекторы карточки товара — при смене вёрстки чинить здесь
_CARD = "form.product_brief_block"
_TITLE = ".prdbrief_name"
_LINK = 'a[href*="/product/"]'
_PRICE_INPUT = "input.product_price"
_PRICE_TEXT = ".prdbrief_price"
_IMAGE = "img"
# Признаки отсутствия товара в наличии (в тексте карточки)
_OOS_MARKERS = ("нет в наличии", "под заказ", "ожидает", "нет на склад")


def parse_listing(html: str, base_url: str) -> list[ParsedOffer]:
    """Извлекает предложения со страницы категории mangoost."""
    tree = HTMLParser(html)
    h1 = tree.css_first("h1")
    category = (h1.text().strip() if h1 else None) or None
    offers: list[ParsedOffer] = []
    for card in tree.css(_CARD):
        external_id = card.attributes.get("rel")
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
                price=_card_price(card),
                in_stock=not _is_out_of_stock(card.text()),
                raw_category=category,
                image_url=urljoin(base_url, image_src) if image_src else None,
            )
        )
    return offers


def _card_price(card: object) -> Decimal | None:
    """Цена из input.product_price (числовое value), с фолбэком на текст блока цены."""
    price_input = card.css_first(_PRICE_INPUT)  # type: ignore[attr-defined]
    if price_input is not None:
        value = parse_price(price_input.attributes.get("value"))
        if value is not None:
            return value
    price_text = card.css_first(_PRICE_TEXT)  # type: ignore[attr-defined]
    return parse_price(price_text.text() if price_text else None)


def _is_out_of_stock(text: str | None) -> bool:
    low = (text or "").lower()
    return any(marker in low for marker in _OOS_MARKERS)


class MangoostParser(ShopParser):
    code: ClassVar[str] = "mangoost"
    name: ClassVar[str] = "Мангуст-Аирсофт"
    base_url: ClassVar[str] = "https://www.mangoost-airsoft.ru"

    home_url: ClassVar[str] = "https://www.mangoost-airsoft.ru/"
    user_agent: ClassVar[str] = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) airsoft_kitfinder-bot"
    )
    request_delay: ClassVar[float] = 0.7

    async def iter_offers(self) -> AsyncIterator[ParsedOffer]:
        """Собирает категории и обходит каждую одной страницей (суффикс /all/)."""
        headers = {"User-Agent": self.user_agent}
        seen_offer_ids: set[str] = set()
        async with httpx.AsyncClient(
            headers=headers, timeout=25.0, follow_redirects=True
        ) as client:
            home = await self._fetch(client, self.home_url)
            if home is None:
                return
            for category_url in self._category_urls(home):
                html = await self._fetch(client, urljoin(category_url, "all/"))
                if html is None:
                    continue
                for offer in parse_listing(html, self.base_url):
                    if offer.external_id not in seen_offer_ids:
                        seen_offer_ids.add(offer.external_id)
                        yield offer

    def _category_urls(self, html: str) -> list[str]:
        """Ссылки категорий (дедуп, порядок сохранён)."""
        tree = HTMLParser(html)
        result: list[str] = []
        seen: set[str] = set()
        for anchor in tree.css('a[href*="/category/"]'):
            href = anchor.attributes.get("href") or ""
            full = urljoin(self.base_url, href)
            if "/category/" in full and full not in seen:
                seen.add(full)
                result.append(full)
        return result

    async def _fetch(self, client: httpx.AsyncClient, url: str) -> str | None:
        await asyncio.sleep(self.request_delay)
        try:
            response = await client.get(url)
        except httpx.HTTPError:
            return None
        if response.status_code != 200:
            return None
        return response.text
