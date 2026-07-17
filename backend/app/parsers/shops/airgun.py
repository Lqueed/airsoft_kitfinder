"""Парсер магазина air-gun.ru (самописная CMS «Conterns», статичный рендер).

Оружейный/пневмо-магазин; парсим ТОЛЬКО страйкбол (весь раздел `/airsoft/`) плюс
релевантное снаряжение (одежда, обувь, навесное — бронежилеты/плитники, подсумки)
из общих разделов `/odejda/` и `/podsumki-*`. Пневматика, боевое, охотничье и т.п.
лежат в других топ-разделах и не обходятся. Категории заданы явным белым списком —
это безопаснее авто-обхода меню (риск затянуть неигровое оружие).

Каталог отдаётся одной страницей на категорию через GET-параметр `?limit=<много>`
(сервер честно рендерит весь список, как `/all/` у mangoost). `raw_category` (h1)
сохраняется — финальная фильтрация возможна на слое матчинга.

`parse_listing` — чистая функция извлечения (тестируется на фикстуре).

Витрина popadiv10.ru — та же площадка (тот же каталог и `data-id`), отдельным
магазином не заводится.
"""

import asyncio
from collections.abc import AsyncIterator
from typing import ClassVar
from urllib.parse import urljoin

import httpx
from selectolax.parser import HTMLParser

from app.parsers.base import ParsedOffer, ShopParser, parse_price

# Селекторы карточки товара в листинге — при смене вёрстки чинить здесь
_CARD = "div.product"
_TITLE_LINK = ".product__name a"
_PRICE = ".product__price"  # текущая цена; старая (зачёркнутая) — .product__oldprice
_IMAGE = ".product__thumb img"
_STOCK_BLOCK = ".product__bot"


def parse_listing(html: str, base_url: str) -> list[ParsedOffer]:
    """Извлекает предложения со страницы категории air-gun.ru."""
    tree = HTMLParser(html)
    h1 = tree.css_first("h1")
    category = (h1.text().strip() if h1 else None) or None
    offers: list[ParsedOffer] = []
    for card in tree.css(_CARD):
        id_node = card.css_first("[data-id]")
        external_id = id_node.attributes.get("data-id") if id_node else None
        link = card.css_first(_TITLE_LINK)
        if not external_id or link is None:
            continue
        title = link.text().strip()
        if not title:
            continue
        price_node = card.css_first(_PRICE)
        image = card.css_first(_IMAGE)
        image_src = None
        if image is not None:
            image_src = image.attributes.get("data-src") or image.attributes.get("src")
        offers.append(
            ParsedOffer(
                external_id=external_id,
                url=urljoin(base_url, link.attributes.get("href") or ""),
                title=title,
                price=parse_price(price_node.text() if price_node else None),
                in_stock=_is_in_stock(card),
                raw_category=category,
                image_url=urljoin(base_url, image_src) if image_src else None,
            )
        )
    return offers


def _is_in_stock(card: object) -> bool:
    """Наличие по тексту блока статуса («В наличии» = да; «Под заказ»/иное = нет)."""
    block = card.css_first(_STOCK_BLOCK)  # type: ignore[attr-defined]
    if block is None:
        return False
    return "в наличии" in block.text().lower()


class AirgunParser(ShopParser):
    code: ClassVar[str] = "airgun"
    name: ClassVar[str] = "Air-Gun"
    base_url: ClassVar[str] = "https://www.air-gun.ru"

    # Белый список категорий: весь страйкбол + релевантное снаряжение.
    # Оружие/пневматика — в других топ-разделах, здесь не обходятся.
    category_paths: ClassVar[tuple[str, ...]] = (
        # Страйкбол (весь раздел /airsoft — приводы 6 мм, не боевое)
        "/airsoft/avtomatyi",
        "/airsoft/vintovki",
        "/airsoft/pistoletyi",
        "/airsoft/pistoletyi_co2",
        "/airsoft/pistoletyi_grin-gaz",
        "/airsoft/pistoletyi-pulemtyi",
        "/airsoft/rujya",
        "/airsoft/granatometyi",
        "/airsoft/magazinyi",
        "/airsoft/akkumulyatoryi",
        "/airsoft/vneshniy_tyuning_obves",
        "/airsoft/zaschita_maski_i_pr",
        "/airsoft/takticheskie_snaryajenie",
        # Снаряжение/одежда/обувь/навесное
        "/odejda/bronezhilety",
        "/odejda/takticheskie_zhilety",
        "/odejda/zhilety",
        "/odejda/obuv",
        "/odejda/nakolenniki_i_nalokotniki",
        "/odejda/perchatki",
        "/odejda/maski",
        "/odejda/golovnyie_uboryi",
        "/odejda/kostyumyi",
        "/odejda/kurtki",
        "/odejda/bryuki_i_shtanyi",
        "/odejda/sumki_i_ryukzaki",
        # Подсумки (общие топ-разделы)
        "/podsumki-takticheskie",
        "/podsumki-universalnye",
        "/podsumki-armeyskie",
        "/podsumki-dlya-pistoletnyh-magazinov",
    )
    user_agent: ClassVar[str] = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) airsoft_kitfinder-bot"
    )
    request_delay: ClassVar[float] = 0.7
    # Каталог отдаётся одной страницей: ставим заведомо больший лимит, чем товаров.
    page_limit: ClassVar[int] = 100000

    async def iter_offers(self) -> AsyncIterator[ParsedOffer]:
        """Обходит белый список категорий, каждую — одной страницей `?limit=`."""
        headers = {"User-Agent": self.user_agent}
        seen_offer_ids: set[str] = set()
        async with httpx.AsyncClient(
            headers=headers, timeout=40.0, follow_redirects=True
        ) as client:
            for path in self.category_paths:
                url = f"{urljoin(self.base_url, path)}?limit={self.page_limit}"
                html = await self._fetch(client, url)
                if html is None:
                    continue
                for offer in parse_listing(html, self.base_url):
                    if offer.external_id not in seen_offer_ids:
                        seen_offer_ids.add(offer.external_id)
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
