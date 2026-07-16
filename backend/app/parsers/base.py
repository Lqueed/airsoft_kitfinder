"""Контракт парсера магазина: DTO предложения и базовый класс-плагин."""

import re
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
    """Извлекает цену из строки, учитывая копейки и разделители тысяч.

    Примеры: '29 500 ₽' → 29500; '949.05 руб.' → 949.05; '1 688,15' → 1688.15.
    Разделитель тысяч (пробел или точка/запятая перед 3 цифрами) отбрасывается;
    точка/запятая перед 1-2 цифрами трактуется как десятичный разделитель.
    Возвращает None, если цифр в строке нет.
    """
    if not text:
        return None
    s = re.sub(r"[^\d.,]", "", re.sub(r"\s", "", text))  # убрать валюту и пробелы
    s = s.strip(".,")  # отбросить хвостовые разделители (напр. точку от «руб.»)
    if not s:
        return None
    if "," in s and "." in s:
        # оба разделителя: правый — десятичный, левый — тысячи
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        head, _, tail = s.rpartition(",")
        s = f"{head}.{tail}" if len(tail) in (1, 2) else s.replace(",", "")
    elif "." in s:
        head, _, tail = s.rpartition(".")
        if len(tail) not in (1, 2):
            s = s.replace(".", "")  # точка как разделитель тысяч
    try:
        return Decimal(s)
    except InvalidOperation:
        return None
