"""Парсер магазина strikeplanet.ru (1C-Bitrix, статичный рендер каталога).

Товары отрендерены в HTML server-side — используем httpx + selectolax, без браузера.
`parse_listing` — чистая функция извлечения (тестируется на фикстуре);
`iter_offers` — обход дерева каталога с пагинацией и rate-limit.
"""

import asyncio
from collections.abc import AsyncIterator
from typing import ClassVar
from urllib.parse import urljoin, urlparse

import httpx
from selectolax.parser import HTMLParser

from app.parsers.base import ParsedOffer, ShopParser, parse_price

# Селекторы карточки товара — при смене вёрстки чинить здесь
_CARD = ".products-card"
_LINK = ".products-card__link"
_TITLE = ".products-card__title"
_PRICE = ".price"
_IN_STOCK = ".cart--add"  # кнопка «в корзину» присутствует у товара в наличии


def parse_listing(html: str, base_url: str) -> list[ParsedOffer]:
    """Извлекает предложения со страницы листинга категории."""
    tree = HTMLParser(html)
    breadcrumb = _extract_breadcrumb(tree)
    offers: list[ParsedOffer] = []
    for card in tree.css(_CARD):
        external_id = card.attributes.get("data-element-id")
        link = card.css_first(_LINK)
        title_node = card.css_first(_TITLE)
        if not external_id or link is None or title_node is None:
            continue  # битая карточка — пропускаем, не роняя прогон
        href = link.attributes.get("href") or ""
        price_node = card.css_first(_PRICE)
        offers.append(
            ParsedOffer(
                external_id=external_id,
                url=urljoin(base_url, href),
                title=title_node.text().strip(),
                price=parse_price(price_node.text() if price_node else None),
                in_stock=card.css_first(_IN_STOCK) is not None,
                raw_category=breadcrumb,
                image_url=_extract_image(card, base_url),
            )
        )
    return offers


def _extract_breadcrumb(tree: HTMLParser) -> str | None:
    """Хлебные крошки страницы — подсказка для матчинга категории."""
    crumbs = [n.text().strip() for n in tree.css(".breadcrumbs a, .breadcrumb a")]
    crumbs = [c for c in crumbs if c and c.lower() not in {"главная", "каталог"}]
    return " / ".join(crumbs) if crumbs else None


def _extract_image(card: object, base_url: str) -> str | None:
    """Ссылка на изображение товара (пропускаем служебные бейджи вроде new.svg)."""
    for img in card.css("img"):  # type: ignore[attr-defined]
        src = img.attributes.get("data-src") or img.attributes.get("src")
        if src and "/img/" not in src and src.endswith((".jpg", ".jpeg", ".png", ".webp")):
            return urljoin(base_url, src)
    return None


class StrikeplanetParser(ShopParser):
    code: ClassVar[str] = "strikeplanet"
    name: ClassVar[str] = "StrikePlanet"
    base_url: ClassVar[str] = "https://strikeplanet.ru"

    # Корень каталога — точка входа обхода дерева категорий
    catalog_root: ClassVar[str] = "https://strikeplanet.ru/catalog/"
    user_agent: ClassVar[str] = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) airsoft_kitfinder-bot"
    )
    request_delay: ClassVar[float] = 0.7  # пауза между запросами, сек
    max_pages_per_category: ClassVar[int] = 50  # предохранитель от бесконечной пагинации

    async def iter_offers(self) -> AsyncIterator[ParsedOffer]:
        """Обходит дерево каталога и отдаёт все предложения (с дедупом по URL)."""
        headers = {"User-Agent": self.user_agent}
        seen_offer_ids: set[str] = set()
        visited: set[str] = {self.catalog_root}
        frontier: list[str] = [self.catalog_root]

        async with httpx.AsyncClient(
            headers=headers, timeout=20.0, follow_redirects=True
        ) as client:
            while frontier:
                category_url = frontier.pop()
                async for offer in self._iter_category(client, category_url, visited, frontier):
                    if offer.external_id not in seen_offer_ids:
                        seen_offer_ids.add(offer.external_id)
                        yield offer

    async def _iter_category(
        self,
        client: httpx.AsyncClient,
        category_url: str,
        visited: set[str],
        frontier: list[str],
    ) -> AsyncIterator[ParsedOffer]:
        """Парсит все страницы одной категории и пополняет frontier подкатегориями."""
        for page in range(1, self.max_pages_per_category + 1):
            url = category_url if page == 1 else f"{category_url}?PAGEN_1={page}"
            html = await self._fetch(client, url)
            if html is None:
                break
            if page == 1:
                self._enqueue_subcategories(html, visited, frontier)
            offers = parse_listing(html, self.base_url)
            if not offers:
                break  # страниц с товарами больше нет
            for offer in offers:
                yield offer

    def _enqueue_subcategories(
        self, html: str, visited: set[str], frontier: list[str]
    ) -> None:
        """Добавляет ссылки подкатегорий в очередь обхода (без карточек товаров)."""
        tree = HTMLParser(html)
        card_hrefs = {n.attributes.get("href") for n in tree.css(_LINK)}
        for anchor in tree.css("a"):
            href = anchor.attributes.get("href")
            if not href or href in card_hrefs:
                continue
            if not href.startswith("/catalog/") or not href.endswith("/"):
                continue
            full = urljoin(self.base_url, href)
            if urlparse(full).netloc == urlparse(self.base_url).netloc and full not in visited:
                visited.add(full)
                frontier.append(full)

    async def _fetch(self, client: httpx.AsyncClient, url: str) -> str | None:
        """GET с rate-limit и мягкой обработкой ошибок (None при неуспехе)."""
        await asyncio.sleep(self.request_delay)
        try:
            response = await client.get(url)
        except httpx.HTTPError:
            return None
        if response.status_code != 200:
            return None
        return response.text
