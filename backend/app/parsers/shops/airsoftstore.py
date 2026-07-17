"""Парсер магазина airsoftstore.ru (VirtueMart/Joomla, JS-анти-бот-челлендж).

Профильный страйкбол-магазин — парсим весь каталог. httpx получает только
заглушку JS-челленджа (~13 КБ), поэтому HTML добывается через **Playwright**
(реальный браузер исполняет челлендж-скрипт, ставит куку и проходит на www).
Внутри браузера обход дешёвый: каждая категория отдаётся одной страницей через
`?showall=999999`.

`parse_listing` — чистая функция извлечения (тестируется на сохранённой фикстуре,
браузер для теста не нужен). Playwright-часть (`iter_offers`) грузится лениво,
чтобы отсутствие браузера не ломало импорт реестра и тесты `parse_listing`.
"""

import re
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, ClassVar
from urllib.parse import urljoin

from selectolax.parser import HTMLParser

from app.parsers.base import ParsedOffer, ShopParser, parse_price

if TYPE_CHECKING:
    from playwright.async_api import Page

# Селекторы карточки товара в листинге — при смене вёрстки чинить здесь
_CARD = ".thumbnail"
_LINK = ".prodname a"  # текст = название, href = ссылка на карточку
_PRICE = ".newprice"  # текущая цена; старая (зачёркнутая) — .oldprice
_IMAGE = ".prodpic img"
_IN_STOCK_LABEL = ".label.in-stock"  # плашка «Есть в наличии»

# external_id — числовой VirtueMart product_id из onclick: setAnchor('pr_9135')
_ID_RE = re.compile(r"pr_(\d+)")
# Топ-разделы каталога: подкатегории (leaf) имеют второй сегмент пути
_TOP_SECTIONS = (
    "oruzhie",
    "snariazhenie",
    "raskhodnye-materialy",
    "zapchasti-i-tiuning",
    "odezhda",
)
_LEAF_RE = re.compile(r"^/(?:" + "|".join(_TOP_SECTIONS) + r")/[^/?#]+$")


def _external_id(link: object) -> str | None:
    """ID товара из onclick-атрибута ссылки (setAnchor('pr_NNNN'))."""
    onclick = link.attributes.get("onclick") or ""  # type: ignore[attr-defined]
    match = _ID_RE.search(onclick)
    return match.group(1) if match else None


def parse_listing(html: str, base_url: str) -> list[ParsedOffer]:
    """Извлекает предложения со страницы категории airsoftstore."""
    tree = HTMLParser(html)
    h1 = tree.css_first("h1")
    category = (h1.text().strip() if h1 else None) or None
    offers: list[ParsedOffer] = []
    for card in tree.css(_CARD):
        link = card.css_first(_LINK)
        if link is None:
            continue
        external_id = _external_id(link)
        title = link.text().strip()
        if not external_id or not title:
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
                in_stock=card.css_first(_IN_STOCK_LABEL) is not None,
                raw_category=category,
                image_url=urljoin(base_url, image_src) if image_src else None,
            )
        )
    return offers


class AirsoftstoreParser(ShopParser):
    code: ClassVar[str] = "airsoftstore"
    name: ClassVar[str] = "Airsoft Store"
    base_url: ClassVar[str] = "https://www.airsoftstore.ru"

    home_url: ClassVar[str] = "https://airsoftstore.ru/"  # редиректит на www через челлендж
    user_agent: ClassVar[str] = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    )
    nav_timeout_ms: ClassVar[int] = 40000
    show_all: ClassVar[int] = 999999  # вся категория одной страницей

    async def iter_offers(self) -> AsyncIterator[ParsedOffer]:
        """Через Playwright проходит челлендж, обходит leaf-категории каталога."""
        from playwright.async_api import async_playwright

        seen_offer_ids: set[str] = set()
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(user_agent=self.user_agent, locale="ru-RU")
            page = await context.new_page()
            page.set_default_timeout(self.nav_timeout_ms)
            try:
                await page.goto(self.home_url, wait_until="domcontentloaded")
                # дождаться прохождения челленджа: появится меню каталога
                await page.wait_for_selector("a[href^='/oruzhie']", timeout=self.nav_timeout_ms)
                for category_url in await self._collect_categories(page):
                    async for offer in self._iter_category(page, category_url):
                        if offer.external_id not in seen_offer_ids:
                            seen_offer_ids.add(offer.external_id)
                            yield offer
            finally:
                await context.close()
                await browser.close()

    async def _collect_categories(self, page: "Page") -> list[str]:
        """Собирает URL leaf-категорий (два сегмента пути) из меню каталога."""
        hrefs: list[str] = await page.eval_on_selector_all(
            "a[href]", "els => els.map(e => e.getAttribute('href'))"
        )
        result: list[str] = []
        seen: set[str] = set()
        for href in hrefs:
            if href and _LEAF_RE.match(href):
                full = urljoin(self.base_url, href)
                if full not in seen:
                    seen.add(full)
                    result.append(full)
        return result

    async def _iter_category(self, page: "Page", category_url: str) -> AsyncIterator[ParsedOffer]:
        url = f"{category_url}?showall={self.show_all}"
        try:
            await page.goto(url, wait_until="domcontentloaded")
        except Exception:
            return
        html = await page.content()
        for offer in parse_listing(html, self.base_url):
            yield offer
