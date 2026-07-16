"""Тесты parse_price: копейки, разделители тысяч, валюта, мусор."""

from decimal import Decimal

import pytest

from app.parsers.base import parse_price


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("29 500 ₽", Decimal("29500")),
        ("949.05 руб.", Decimal("949.05")),
        ("1 688.15 руб.", Decimal("1688.15")),
        ("1 371,80", Decimal("1371.80")),
        ("1.234", Decimal("1234")),  # точка как разделитель тысяч (3 цифры)
        ("999 руб.", Decimal("999")),
        ("80", Decimal("80")),
    ],
)
def test_parse_price_valid(text: str, expected: Decimal) -> None:
    assert parse_price(text) == expected


@pytest.mark.parametrize("text", ["", None, "нет цены", "по запросу"])
def test_parse_price_none(text: str | None) -> None:
    assert parse_price(text) is None
