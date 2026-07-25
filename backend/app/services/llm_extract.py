"""LLM-экстракция атрибутов товара из названия (спайк на категории `drive`).

Идея: нейросеть НЕ решает «одинаковы ли два товара», а раскладывает сырое
название на структурные атрибуты (бренд, модель, тип механики, платформа).
Из атрибутов детерминированный Python собирает `match_key` — ровно как уже
сделано для шаров (`bbs`), только атрибуты добывает LLM, а не регулярки.

Слой встраивается перед `matching.build_match_key`; дедуп остаётся
детерминированным и идемпотентным. Результат экстракции кэшируется на диске
по хешу названия — при повторных прогонах/rematch в API не ходим: одно и то же
название всегда даёт один и тот же ключ (кэш «замораживает» ответ, поэтому
ненулевая temperature провайдера не ломает детерминизм дедупа).

Провайдер — GigaChat (Сбер): доступен из РФ, бесплатный тариф для физлиц,
силён на русских названиях. Вызовы идут через httpx (доп. зависимости не нужны).
Всё офлайн, запускается по крону.
"""

import asyncio
import hashlib
import json
import re
import time
import uuid
from pathlib import Path
from typing import Any

import httpx

from app.config import settings

_OAUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
_CHAT_URL = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"

# Промпт с несколькими примерами — few-shot резко повышает стабильность разбора.
# Схема полей задана прямо в промпте (GigaChat вернёт JSON-объект), парсинг —
# толерантный (снимаем markdown-обрамление, берём первый {...}).
_DRIVE_PROMPT = """Ты извлекаешь канонические атрибуты СТРАЙКБОЛЬНОГО ПРИВОДА из \
названия карточки товара интернет-магазина. Верни ТОЛЬКО JSON-объект с полями:
is_drive (boolean), brand (string), model (string), \
system (одно из: aeg, aep, gbb, gbbr, spring, hpa, co2, dmr, unknown), platform (string).
Без пояснений и markdown — только JSON.

is_drive=true ТОЛЬКО для готового страйкбольного оружия ЦЕЛИКОМ: \
электроавтомат/электропривод/электропистолет (AEG/AEP), газовый пистолет или \
винтовка (GBB/GBBR), пружинная/снайперская винтовка (spring), HPA.
is_drive=false для ЛЮБЫХ запчастей и обвеса: рукоятки, крепления, антабки, \
переходники, поршни, ЦПГ, наборы тюнинга, стволы, резинки хоп-ап, аккумуляторы, \
прицелы, магазины, подсумки, глушители — даже если в названии есть слово «привод».

Правила заполнения (только при is_drive=true):
- brand: производитель латиницей, нижний регистр, без пунктуации и пробелов \
(«CYMA»→«cyma», «G&G»→«gg», «Tokyo Marui»→«tm», «Well»→«well»).
- model: КОРОТКИЙ модельный код производителя, нижний регистр, без пунктуации и \
пробелов. Копируй символы кода ТОЧНО, буква в букву — НЕ переставляй («LCK-16»→\
«lck16», а не «lkc16»). Приоритет — артикул производителя, если он есть в скобках/\
слэшах/в конце названия («(at-cat-06)»→«atcat06», «/CM.093С/»→«cm093», «(CM.030)»→\
«cm030»): он одинаков в разных магазинах. Иначе — узнаваемое обозначение модели \
(«AK19», «CM.610»→«cm610», «Glock 17 Gen4»→«glock17gen4»). НЕ бери внутренние \
числовые SKU («LCT 13732 AK19»→«ak19», не «13732»). НЕ добавляй описательные слова \
и характеристики: тип (rifle, smg, carbine, cqb, pdw, aeg), длину ствола (12.2", \
10"), цвет, ®. Без бренда, платформы и слов «привод/страйкбольный/автомат/пистолет».
- system: aeg (электроавтомат/электропривод), aep (электропистолет), gbb/gbbr \
(газ), spring (пружина/снайперка), hpa, co2, dmr. Если не ясно — «unknown».
- platform: тип/платформа оружия латиницей нижним регистром (ak, ar15, m4, mp5, \
glock, m14, svd, ...). Если не ясно — пустая строка.
Если is_drive=false — остальные поля пустыми строками.

Примеры:
Название: «Страйкбольный автомат CYMA CM.610 (AK-74M)» -> \
{"is_drive":true,"brand":"cyma","model":"cm610","system":"aeg","platform":"ak"}
Название: «CYMA Страйкбольный электропистолет Glock18C (CM.030)» -> \
{"is_drive":true,"brand":"cyma","model":"cm030","system":"aep","platform":"glock"}
Название: «Автомат Arcturus X C.A.T. AR-15 8.5 AR AEG (at-cat-06)» -> \
{"is_drive":true,"brand":"arcturus","model":"atcat06","system":"aeg","platform":"ar15"}
Название: «LCT 13732 AK19 RIFLE AEG AIRSOFT» -> \
{"is_drive":true,"brand":"lct","model":"ak19","system":"aeg","platform":"ak"}
Название: «Пистолет WE Glock 17 Gen4 GBB» -> \
{"is_drive":true,"brand":"we","model":"glock17gen4","system":"gbb","platform":"glock"}
Название: «CYMA Пистолетная рукоятка на М4 /М041/» -> \
{"is_drive":false,"brand":"","model":"","system":"unknown","platform":""}
Название: «ARS Поршень для пружинной винтовки CYMA VSR-10» -> \
{"is_drive":false,"brand":"","model":"","system":"unknown","platform":""}

Название: «{title}»"""

# Бренд-алиасы (латиница/кириллица → канон). Расширяемо; синхронно с matching.
_BRAND_ALIASES: dict[str, str] = {
    "gandg": "gg",
    "g&g": "gg",
    "tokyomarui": "tm",
    "tokyo marui": "tm",
    "сайма": "cyma",
    "кама": "cyma",
    "велл": "well",
}

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def title_hash(title: str) -> str:
    """Ключ кэша: стабильный хеш сырого названия (регистронезависимо)."""
    return hashlib.sha256(title.strip().lower().encode("utf-8")).hexdigest()


def _canon_token(value: str) -> str:
    """Нижний регистр + только латиница/цифры (для бренда и модели)."""
    return _NON_ALNUM_RE.sub("", value.strip().lower())


def canon_brand(brand: str) -> str:
    """Канонизирует бренд через словарь алиасов и очистку токена."""
    low = brand.strip().lower()
    if low in _BRAND_ALIASES:
        return _BRAND_ALIASES[low]
    token = _canon_token(low)
    return _BRAND_ALIASES.get(token, token)


def drive_key(attrs: dict[str, Any]) -> str | None:
    """Строит структурный ключ привода из атрибутов LLM.

    `drive:brand|model|system`. Возвращает None, если LLM счёл это не приводом
    или не распознал бренд/модель — тогда оффер уходит на фолбэк (общий
    токен-нормализатор в matching.py), как и нераспознанные шары.
    """
    if not attrs.get("is_drive"):
        return None
    brand = canon_brand(str(attrs.get("brand", "")))
    model = _canon_token(str(attrs.get("model", "")))
    if not brand or not model:
        return None
    system = str(attrs.get("system") or "unknown")
    return f"drive:{brand}|{model}|{system}"


def _parse_json(text: str) -> dict[str, Any]:
    """Толерантный разбор ответа: снимает ```-обрамление, берёт первый {...}."""
    match = _JSON_RE.search(text)
    if match is None:
        raise json.JSONDecodeError("нет JSON-объекта в ответе", text, 0)
    return json.loads(match.group(0))


class ExtractionCache:
    """Файловый кэш экстракции: хеш названия → {title, attrs, model}.

    Загружается целиком в память в начале прогона, сохраняется в конце.
    Единственный писатель — cron-скрипт, поэтому блокировки не нужны.
    В продакшене переезжает в таблицу `title_extractions`; для спайка — файл.
    """

    def __init__(self, path: str) -> None:
        self._path = Path(path)
        self._data: dict[str, dict[str, Any]] = {}
        self.hits = 0
        self.misses = 0
        if self._path.exists():
            self._data = json.loads(self._path.read_text(encoding="utf-8"))

    def get(self, title: str) -> dict[str, Any] | None:
        entry = self._data.get(title_hash(title))
        if entry is not None:
            self.hits += 1
            return entry["attrs"]
        return None

    def put(self, title: str, attrs: dict[str, Any], model: str) -> None:
        self.misses += 1
        self._data[title_hash(title)] = {"title": title, "attrs": attrs, "model": model}

    def save(self) -> None:
        self._path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=1), encoding="utf-8"
        )


class GigaChatSession:
    """Сессия GigaChat: httpx-клиент + OAuth-токен с автообновлением.

    Токен живёт ~30 минут; обновляем заранее. У GigaChat российский корневой CA,
    поэтому verify берём из настроек (по умолчанию отключён для крон-скрипта).
    Используется как async-контекст: `async with GigaChatSession() as s: ...`.
    """

    def __init__(self) -> None:
        verify: bool | str = settings.gigachat_ca_bundle or settings.gigachat_verify_ssl
        if verify is False:
            print("[GigaChat] TLS-проверка отключена (verify=False) — ок для крона.")
        self._client = httpx.AsyncClient(timeout=30, verify=verify)
        self._token: str = ""
        self._expiry: float = 0.0  # unix-секунды, когда токен протухнет

    async def __aenter__(self) -> "GigaChatSession":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self._client.aclose()

    async def _ensure_token(self) -> None:
        if self._token and time.time() < self._expiry - 60:
            return
        resp = await self._client.post(
            _OAUTH_URL,
            headers={
                "Authorization": f"Basic {settings.gigachat_auth_key}",
                "RqUID": str(uuid.uuid4()),
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            data={"scope": settings.gigachat_scope},
        )
        resp.raise_for_status()
        payload = resp.json()
        self._token = payload["access_token"]
        # expires_at приходит в миллисекундах epoch
        self._expiry = float(payload["expires_at"]) / 1000

    async def complete(self, prompt: str) -> dict[str, Any]:
        """Один вызов чата со structured-промптом; ретраи на 401/429/5xx."""
        body = {
            "model": settings.gigachat_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 200,
        }
        for attempt in range(4):
            await self._ensure_token()
            resp = await self._client.post(
                _CHAT_URL,
                headers={"Authorization": f"Bearer {self._token}"},
                json=body,
            )
            if resp.status_code == 401:
                self._token = ""  # протух — обновим на след. итерации
                continue
            if resp.status_code in (429, 500, 502, 503):
                await asyncio.sleep(2**attempt)
                continue
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"]
            return _parse_json(text)
        resp.raise_for_status()
        raise RuntimeError("GigaChat: исчерпаны ретраи")  # недостижимо, для типов


async def extract_drive(
    session: GigaChatSession, cache: ExtractionCache, title: str
) -> dict[str, Any]:
    """Возвращает атрибуты привода для названия (из кэша или через GigaChat).

    При ошибке API возвращает {"is_drive": false} — оффер уйдёт на фолбэк,
    а не свалит прогон (принцип «парсер не уничтожает данные»).
    """
    cached = cache.get(title)
    if cached is not None:
        return cached
    await asyncio.sleep(settings.llm_request_delay)  # только на промахе кэша
    try:
        # .replace, а не .format: в промпте есть JSON-примеры с фигурными
        # скобками — str.format трактовал бы их как поля подстановки и падал.
        attrs = await session.complete(_DRIVE_PROMPT.replace("{title}", title))
    except (httpx.HTTPError, KeyError, json.JSONDecodeError):
        attrs = {"is_drive": False}
    cache.put(title, attrs, settings.gigachat_model)
    return attrs
