"""Контракт парсера магазина: DTO предложения и базовый класс-плагин."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import ClassVar


@dataclass(slots=True)
class ParsedOffer:
    """Сырое предложение, снятое парсером с карточки магазина.

    Парсер отдаёт только эти данные; нормализация и матчинг с каноническим
    товаром происходят позже в слое services (matching, M3).
    """

    external_id: str  # стабильный ID товара в магазине (артикул/element-id)
    url: str  # абсолютная ссылка на карточку
    title: str  # название как на сайте
    price: Decimal | None  # None, если цена не указана
    in_stock: bool
    raw_category: str | None = None  # хлебные крошки магазина (подсказка для матчинга)
    image_url: str | None = None


class ShopParser(ABC):
    """Базовый плагин парсера. Один подкласс на магазин.

    `code` должен совпадать с `shops.code` в БД и ключом в реестре парсеров.
    """

    code: ClassVar[str]
    name: ClassVar[str]
    base_url: ClassVar[str]

    @abstractmethod
    def iter_offers(self) -> AsyncIterator[ParsedOffer]:
        """Асинхронно отдаёт все предложения магазина (по всем категориям)."""
        raise NotImplementedError


def parse_price(text: str | None) -> Decimal | None:
    """Извлекает цену из строки вида '29 500 ₽' → Decimal('29500').

    Возвращает None, если цифр в строке нет.
    """
    if not text:
        return None
    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        return None
    try:
        return Decimal(digits)
    except InvalidOperation:
        return None
