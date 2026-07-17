"""Генерация URL-слагов из русских названий (транслитерация)."""

import re

# Латинизация кириллицы для URL-слага.
_TRANSLIT: dict[str, str] = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ж": "zh",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n",
    "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f",
    "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y",
    "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def slugify(name: str, *, max_length: int = 80, fallback: str = "kit") -> str:
    """URL-слаг из названия: транслит кириллицы, нижний регистр, дефисы вместо прочего."""
    base = "".join(_TRANSLIT.get(ch, ch) for ch in name.lower())
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")[:max_length].strip("-")
    return base or fallback
