# airsoft_kitfinder — реестр магазинов для парсинга

Список магазинов-источников и их статус. Архитектура парсеров плагинная
(см. [ARCHITECTURE.md](ARCHITECTURE.md)), поэтому список расширяемый.
Разведка проведена 2026-07-16, дополнена 2026-07-17 (статусы могут меняться).

Обозначения рендера: **static** — товары в исходном HTML (httpx + selectolax);
**JS** — нужен headless-браузер (Playwright); **?** — требует проверки.

## Реализованные

| Магазин | URL | Платформа | Рендер | Статус |
|---|---|---|---|---|
| StrikePlanet | strikeplanet.ru | 1C-Bitrix | static | ✅ парсер готов (M2) |
| Zorg | zorg.pro | 1C-Bitrix | static | ✅ парсер готов (M3); каталог плоский, цены с копейками |
| Мангуст-Аирсофт | mangoost-airsoft.ru | UMI.CMS | static | ✅ парсер готов (M3); категории одной страницей `/all/` |
| Air-Gun | air-gun.ru | Conterns (самописная) | static | ✅ парсер готов (2026-07-17); только `/airsoft/*` + снаряжение (одежда/обувь/бронежилеты/подсумки), категория одной страницей `?limit=` |
| Пневмат24 | pnevmat24.ru | OpenCart | static | ✅ парсер готов (2026-07-17); только раздел снаряжения `/snaryazhenie-i-odezhda/*`, пагинация `?page=` |
| Airsoft Store | airsoftstore.ru | VirtueMart (Joomla) | **JS/Playwright** | ✅ парсер готов (2026-07-17); профильный (весь каталог); браузер проходит JS-челлендж, категория одной страницей `?showall=999999` |

> Код магазина = имя файла парсера (`app/parsers/shops/<code>.py`) и ключ в реестре:
> `strikeplanet`, `zorg`, `mangoost`, `airgun`, `pnevmat24`, `airsoftstore`.

> **Playwright-парсер** (`airsoftstore`) — первый, кому нужен реальный браузер.
> Плагинная архитектура это поддерживает без изменений реестра/ingest: `parse_listing`
> остаётся чистой функцией (тест на фикстуре), а `iter_offers` добывает HTML через
> Playwright (headless chromium, ленивый импорт). Требует `playwright install chromium`.
> Селекторы: карточка `.thumbnail`; название/ссылка `.prodname a`; цена `.newprice`
> (старая — `.oldprice`); наличие — плашка `.label.in-stock`; картинка `.prodpic img`;
> `external_id` — VirtueMart product_id из `onclick="setAnchor('pr_NNNN')"`. Категории
> собираются с главной автоматически (leaf = второй сегмент пути в топ-разделах
> `oruzhie/snariazhenie/raskhodnye-materialy/zapchasti-i-tiuning/odezhda`).

## В очереди — нужен Playwright (JS-анти-бот)

httpx получает только заглушку-челлендж; реальный браузер проходит проверку и ставит куку.

| Магазин | URL | Детали |
|---|---|---|
| Airsoft-RUS | airsoft-rus.ru | **Cloudflare managed challenge** («Выполнение проверки безопасности», Ray ID; 403 для httpx). Проверено 2026-07-17: обычный headless-Playwright челлендж **не проходит** (CF детектит автоматизацию, кука не ставится и за 20 с). Нужен undetected/stealth-подход или ручной прокидываемый cookie — гонка вооружений, не для крона личного проекта. Браться в последнюю очередь. |

## Недоступны из среды разработки (проверить позже)

Не резолвятся/не отвечают из текущей среды — парсер писать не на чем, пока сайт
недоступен. Проверить с рабочей машины.

| Магазин | URL | Проблема |
|---|---|---|
| 6mm | 6mm.ru | Не резолвится/timeout (ранее отдавал 500). Название = калибр страйкбола, почти наверняка профильный. |
| AirsoftSports | airsoftsports.ru | Не резолвится/timeout (ранее — перегруз их БД, `SQLSTATE 1040 Too many connections`). |

## Отклонённые

- **popadiv10.ru** — не самостоятельный магазин, а витрина-обёртка каталога
  `www.air-gun.ru` (тот же движок Conterns, те же `data-id`, те же товары; каталожные
  пути на самом popadiv10.ru отдают 404). Отдельным источником **не заводим** — это
  задвоило бы офферы Air-Gun. Разведку по popadiv10.ru повторять не нужно.
- **ana-team.ru**, **militarist.ru** — исключены из списка.

## Порядок реализации остатка

1. **airsoftstore.ru** — Playwright-парсер (структура и селекторы разобраны выше).
2. **airsoft-rus.ru** — в последнюю очередь (Cloudflare, Playwright).
3. **6mm.ru**, **airsoftsports.ru** — после восстановления доступности.
