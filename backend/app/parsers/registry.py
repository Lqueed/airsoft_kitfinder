"""Явный реестр парсеров магазинов. Добавить магазин = импорт + строка здесь."""

from app.parsers.base import ShopParser
from app.parsers.shops.mangoost import MangoostParser
from app.parsers.shops.strikeplanet import StrikeplanetParser
from app.parsers.shops.zorg import ZorgParser

PARSERS: dict[str, type[ShopParser]] = {
    StrikeplanetParser.code: StrikeplanetParser,
    ZorgParser.code: ZorgParser,
    MangoostParser.code: MangoostParser,
}


def get_parser(code: str) -> type[ShopParser]:
    """Возвращает класс парсера по коду магазина."""
    try:
        return PARSERS[code]
    except KeyError as exc:
        available = ", ".join(sorted(PARSERS)) or "нет"
        raise KeyError(f"Неизвестный магазин '{code}'. Доступны: {available}") from exc
