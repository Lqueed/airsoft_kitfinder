"""Матчинг офферов магазинов в канонические товары (products).

Единственное место нормализации названий. Парсеры отдают сырые данные и никогда
не пишут в products напрямую — товары создаются только здесь.

Стратегия (без ML, ставка на точность, а не полноту):
- нормализуем название в `match_key` (нижний регистр, алиасы брендов, снятие пунктуации
  и шумовых слов, сортировка уникальных токенов);
- офферы с ОДИНАКОВЫМ `match_key` сводятся в один product; иначе создаётся новый.
Спорные случаи (разные формулировки одного товара) не сливаются автоматически —
их доразметит админ вручную (перепривязка оффера). Лучше недо-слить (дубль product),
чем ошибочно слить разные товары.
"""

import hashlib
import re
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import Category, Offer, Product

# Алиасы брендов: приводим написание к единому виду ДО снятия пунктуации,
# чтобы «G&G», «E&L» не рассыпались на отдельные токены.
_BRAND_ALIASES: dict[str, str] = {
    "g&g": "gg",
    "e&l": "el",
    "d&g": "dg",
    "s&t": "st",
    "tokyo marui": "tm",
}

# Шумовые слова, не несущие модельной информации (убираем из match_key).
_STOP_WORDS: frozenset[str] = frozenset(
    {
        "страйкбольный",
        "страйкбольная",
        "страйкбольное",
        "страйкбольные",
        "airsoft",
        "для",
        "и",
        "с",
        "в",
        "на",
        "шт",
        "новый",
        "новинка",
        "привода",
        "приводов",
        "пистолетов",
    }
)

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)

# Ключевые слова → slug нашей категории (эвристика назначения категории товару).
_CATEGORY_KEYWORDS: list[tuple[tuple[str, ...], str]] = [
    (("шар", "bb"), "bbs"),
    (("маск", "очки", "защита глаз"), "eyewear"),
    (("шлем", "каск"), "helmet"),
    (("перчат",), "gloves"),
    (("наколен", "налокот"), "knee_pads"),
    (("аккумулятор", "батаре", "зарядн"), "battery"),
    (("магазин бункер", "магазин механ", "бункер"), "magazines"),
    (("граната",), "grenades"),
    (("рация", "радиостанц"), "radio"),
    (("подсумок", "подсумк"), "pouches"),
    (("разгрузк", "жилет", "чрн", "плитоноск"), "rig"),
    (("ботинк", "берцы", "обувь"), "boots"),
    (("китель", "форма", "костюм", "футболк", "брюки"), "uniform"),
    (("автомат", "привод", "пистолет", "винтовк", "пулемет", "дробовик", "оружие"), "drive"),
]

# --- Структурный ключ для шаров (bbs) --------------------------------------
# У шаров название физически задаётся брендом + весом + цветом + типом
# (трассер/обычный); фасовка, кол-во штук и артикул магазина — шум для матчинга
# (это варианты одного товара). Поэтому для категории bbs ключ строим
# структурно, а не из полного набора токенов — иначе один товар в разных
# магазинах никогда не сходится (разный формат веса, язык, артикулы).

# Бренды шаров + алиасы (в т.ч. кириллические/латинские дубли). Ищутся как
# подстрока в нижнем регистре названия; порядок важен — длинные раньше.
_BBS_BRANDS: list[tuple[str, str]] = [
    ("angry bbs", "angry"),
    ("angry", "angry"),
    ("novritsch", "novritsch"),
    ("mad bull", "madbull"),
    ("madbull", "madbull"),
    ("top power", "toppower"),
    ("g&g", "gg"),
    ("exact", "exact"),
    ("azot", "azot"),  # латинская A
    ("аzot", "azot"),  # кириллическая А (как на mangoost)
    ("азот", "azot"),
    ("bls", "bls"),
    ("vfc", "vfc"),
    ("stti", "stti"),
    ("ace", "ace"),
    ("stalker", "stalker"),
]

# Цвет шара + алиасы рус/англ. Дефолт — белый: StrikePlanet цвет не указывает,
# а обычные шары по умолчанию белые (порядок важен — «слоновая кость» раньше «сер»).
_BBS_COLORS: list[tuple[str, str]] = [
    ("слоновая кость", "ivory"),
    ("ivory", "ivory"),
    ("зелен", "green"),
    ("green", "green"),
    ("красн", "red"),
    ("red", "red"),
    ("сер", "gray"),
    ("gray", "gray"),
    ("grey", "gray"),
    ("бел", "white"),
    ("white", "white"),
]

# Вес шара: ведущий «0.NN», не часть большего числа. Единица (г/гр/g) необязательна —
# ведущий «0.» уже отсекает фасовку («1 кг», «4000 шт») и сувенирный «.50 Cal».
_BBS_WEIGHT_RE = re.compile(r"(?<!\d)0[.,](\d{1,2})(?!\d)")
_BBS_TRACER_RE = re.compile(r"трассер|трассир|tracer", re.IGNORECASE)


def _bbs_brand(title: str) -> str | None:
    """Канонический код бренда шара по словарю алиасов. None — если не распознан."""
    low = title.lower()
    for needle, canonical in _BBS_BRANDS:
        if needle in low:
            return canonical
    return None


def _bbs_weight(title: str) -> float | None:
    """Вес шара в граммах (0.30г / 0,3 гр / bbs0.50g → 0.3). None — если не найден."""
    m = _BBS_WEIGHT_RE.search(title)
    if not m:
        return None
    return float("0." + m.group(1).ljust(2, "0"))


def _bbs_color(title: str) -> str:
    """Цвет шара по словарю алиасов; дефолт 'white', если цвет не указан."""
    low = title.lower()
    for needle, canonical in _BBS_COLORS:
        if needle in low:
            return canonical
    return "white"


def bbs_match_key(title: str) -> tuple[str, dict[str, object]] | None:
    """Структурный ключ шара и его атрибуты: `bbs:brand|weight|color|tracer`.

    Возвращает None, если бренд или вес не распознаны — тогда это, скорее всего,
    не шар (лоадер/мишень/подсумок из той же категории сайта) либо неизвестный
    бренд; такой оффер уходит на фолбэк-нормализацию по общему правилу.
    """
    brand = _bbs_brand(title)
    weight = _bbs_weight(title)
    if brand is None or weight is None:
        return None
    color = _bbs_color(title)
    tracer = bool(_BBS_TRACER_RE.search(title))
    key = f"bbs:{brand}|{weight}|{color}|{'t' if tracer else 'n'}"
    attrs: dict[str, object] = {"brand": brand, "weight": weight, "color": color, "tracer": tracer}
    return key, attrs


# Латинизация кириллицы для URL-слага товара.
_TRANSLIT = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "h",
    "ц": "c",
    "ч": "ch",
    "ш": "sh",
    "щ": "sch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}


@dataclass(slots=True)
class MatchReport:
    """Сводка прогона матчинга."""

    processed: int = 0
    linked_existing: int = 0
    created_products: int = 0
    errors: list[str] = field(default_factory=list)


def normalize_title(title: str) -> str:
    """Приводит название к каноническому `match_key`.

    Регистронезависимо, ё→е, алиасы брендов, снятие пунктуации и шумовых слов,
    сортировка уникальных токенов (порядок слов не влияет).
    """
    text = title.lower().replace("ё", "е")
    for alias, canonical in _BRAND_ALIASES.items():
        text = text.replace(alias, canonical)
    text = _PUNCT_RE.sub(" ", text)
    tokens = sorted({t for t in text.split() if t and t not in _STOP_WORDS})
    return " ".join(tokens)


def guess_category_slug(*texts: str | None) -> str | None:
    """Определяет slug категории по ключевым словам в названии/крошках."""
    haystack = " ".join(t.lower() for t in texts if t)
    for keywords, slug in _CATEGORY_KEYWORDS:
        if any(kw in haystack for kw in keywords):
            return slug
    return None


def _slugify(name: str, match_key: str) -> str:
    """URL-слаг товара: латинизированное имя + короткий хеш match_key для уникальности."""
    base = "".join(_TRANSLIT.get(ch, ch) for ch in name.lower())
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")[:80]
    digest = hashlib.md5(match_key.encode("utf-8")).hexdigest()[:8]  # noqa: S324
    return f"{base}-{digest}" if base else digest


async def _category_map(session: AsyncSession) -> dict[str, int]:
    """Кэш {slug категории → id}."""
    rows = await session.execute(select(Category.slug, Category.id))
    return {slug: cid for slug, cid in rows.all()}


def build_match_key(raw_title: str, category_slug: str | None) -> tuple[str, dict[str, object]]:
    """Ключ матчинга и структурные атрибуты товара по названию и категории.

    Для шаров (bbs) — структурный ключ (бренд+вес+цвет+тип); если он не собрался
    (неизвестный бренд / это не шар), а также для всех прочих категорий — общий
    нормализатор `normalize_title`. Атрибуты непусты только для распознанных шаров.
    """
    if category_slug == "bbs":
        result = bbs_match_key(raw_title)
        if result is not None:
            return result
    return normalize_title(raw_title), {}


async def match_offer(
    session: AsyncSession, offer: Offer, categories: dict[str, int]
) -> tuple[Product, bool]:
    """Привязывает оффер к товару по match_key (find-or-create). Возвращает (product, created)."""
    slug = guess_category_slug(offer.raw_category, offer.raw_title)
    match_key, attrs = build_match_key(offer.raw_title, slug)
    product = await session.scalar(select(Product).where(Product.match_key == match_key))
    created = False
    if product is None:
        product = Product(
            name=offer.raw_title,
            slug=_slugify(offer.raw_title, match_key),
            match_key=match_key,
            category_id=categories.get(slug) if slug else None,
            brand=attrs.get("brand") if attrs else None,
            attrs=attrs,
            image_url=offer.image_url,
        )
        session.add(product)
        await session.flush()
        created = True
    elif product.image_url is None and offer.image_url is not None:
        product.image_url = offer.image_url  # дозаполняем картинку из оффера
    offer.product_id = product.id
    return product, created


async def create_product_from_offer(session: AsyncSession, offer: Offer) -> tuple[Product, bool]:
    """Создаёт (или находит) канонический товар из оффера и привязывает оффер.

    Тонкая обёртка над `match_offer` — соблюдает инвариант «products создаются
    только через matching.py» и не дублирует генерацию slug/match_key. Если товар
    с таким `match_key` уже есть, привязывает к нему (created=False), не плодя дубль.
    Коммит — на вызывающей стороне (эндпоинте).
    """
    categories = await _category_map(session)
    return await match_offer(session, offer, categories)


async def match_unmatched(session: AsyncSession, shop_id: int | None = None) -> MatchReport:
    """Матчит все офферы без товара (product_id IS NULL). Идемпотентно."""
    report = MatchReport()
    categories = await _category_map(session)

    stmt = select(Offer).where(Offer.product_id.is_(None))
    if shop_id is not None:
        stmt = stmt.where(Offer.shop_id == shop_id)

    for offer in await session.scalars(stmt):
        report.processed += 1
        _product, created = await match_offer(session, offer, categories)
        if created:
            report.created_products += 1
        else:
            report.linked_existing += 1

    await session.commit()
    return report
