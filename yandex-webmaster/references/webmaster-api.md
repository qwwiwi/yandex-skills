# Yandex Webmaster API v4 – Reference

> Source: official Yandex Webmaster developer docs (yandex.com/dev/webmaster/doc/en/, RU mirror yandex.ru/dev/webmaster/doc/ru/). Cross-verified June 2026. Items the docs don't pin down are marked **(verify against live API)**. Основные вызовы проверялись на живом API при подготовке скилла; остальное – по документации.

## 0. Conventions

| Thing | Value |
|---|---|
| Base URL | `https://api.webmaster.yandex.net` |
| Version prefix | `/v4` |
| Auth header | `Authorization: OAuth <token>` (literal word `OAuth`, not `Bearer`). Токен – из переменной `YANDEX_OAUTH_TOKEN`. |
| {user-id} | int64 – from `GET /v4/user`. Скрипт определяет его сам. |
| {host-id} | string `protocol:host:port`, no slashes. Например `https:example.com:443`. **URL-encode** when embedding in a path. |

**Mandatory first call:** `GET /v4/user` → user_id (cache). Then `GET /v4/user/{user-id}/hosts` to map domain→host_id.
**Dates:** request `date_from`/`date_to` as `YYYY-MM-DD`. Responses return ISO-8601 with TZ.

---

## 1. User & Hosts
- `GET /v4/user` → `{user_id}`. Bootstrap.
- `GET /v4/user/{uid}/hosts` → `{hosts:[{host_id, ascii_host_url, unicode_host_url, verified, main_mirror}]}`. Resolve domain→host_id.
- `POST /v4/user/{uid}/hosts` body `{host_url}` → `201 {host_id}`. Add a site. Errors 403 HOSTS_LIMIT_EXCEEDED, 409 HOST_ALREADY_ADDED.
- `GET /v4/user/{uid}/hosts/{hid}` → host info incl. **`host_data_status` (NOT_INDEXED|NOT_LOADED|OK)** – check = OK before trusting data endpoints.
- `DELETE /v4/user/{uid}/hosts/{hid}` → 204.
- `GET /v4/user/{uid}/hosts/{hid}/verification` → `{verification_uin, verification_state (NONE|VERIFIED|IN_PROGRESS|VERIFICATION_FAILED|INTERNAL_ERROR), verification_type, applicable_verifiers[]}`.
- `POST /v4/user/{uid}/hosts/{hid}/verification?verification_type=DNS|HTML_FILE|META_TAG` → starts verification.
- `GET /v4/user/{uid}/hosts/{hid}/owners` → who verified the site.

## 2. Summary (ИКС/SQI + counts) – one-call health snapshot
`GET /v4/user/{uid}/hosts/{hid}/summary` →
```json
{ "sqi": 0, "searchable_pages_count": 0, "excluded_pages_count": 0,
  "site_problems": {"FATAL":0,"CRITICAL":0,"POSSIBLE_PROBLEM":0,"RECOMMENDATION":0} }
```
**Индексированные/исключённые страницы живут ЗДЕСЬ** (в группе /indexing нет агрегатного счётчика). `GET .../sqi-history?date_from=&date_to=` → ряд ИКС во времени.

## 3. Search queries – SEO-золото
Общие enum: `query_indicator` (повторяемый) = `TOTAL_SHOWS|TOTAL_CLICKS|AVG_SHOW_POSITION|AVG_CLICK_POSITION`; `device_type_indicator` = `ALL|DESKTOP|MOBILE|TABLET|MOBILE_AND_TABLET`.
- `GET .../search-queries/popular` – ранжированный список (ТОП-3000 за неделю, тянуть до 500). Params: **`order_by` REQUIRED = TOTAL_SHOWS|TOTAL_CLICKS** (НЕ AVG_*), `query_indicator` (repeat), `device_type_indicator`, `date_from`/`date_to`, `limit` 1–500 (max 500), `offset`. → `{queries:[{query_id, query_text, indicators{...}}], count}`.
- `GET .../search-queries/all/history` – суммарная динамика. Params: `query_indicator`(repeat), `device_type_indicator`, `date_from`/`date_to`. НЕТ order_by/limit. → `{indicators:{TOTAL_SHOWS:[{date,value}],...}}`.
- `GET .../search-queries/{query_id}/history` – динамика одного запроса. Error 404 QUERY_ID_NOT_FOUND.

Позиция: меньше = выше. **Рычаг:** popular(order_by=TOTAL_SHOWS, +AVG_SHOW_POSITION) → клиент-сайд фильтр позиции 4–15 + высокие показы = «почти топ», докрутить контентом (API не фильтрует по позиции).

## 4. Indexing & pages-in-search
Enum `IndexingStatusEnum`: `HTTP_2XX|HTTP_3XX|HTTP_4XX|HTTP_5XX|OTHER`. `ApiExcludedUrlStatus` (14): NOTHING_FOUND, HOST_ERROR, REDIRECT_NOTSEARCHABLE, HTTP_ERROR, NOT_CANONICAL, NOT_MAIN_MIRROR, PARSER_ERROR, ROBOTS_HOST_ERROR, ROBOTS_URL_ERROR, DUPLICATE, LOW_QUALITY, CLEAN_PARAMS, NO_INDEX, OTHER. History = `date_from`/`date_to`; Samples = `offset`/`limit` (1–100, default 50).
- `GET .../indexing/history` → `{indicators:{HTTP_2XX:[{date,value}],HTTP_4XX:[...],...}}` – обход роботом по статусам (ловить всплески 4xx/5xx).
- `GET .../indexing/samples` → `{count, samples:[{url, status, http_code?, access_date}]}`.
- `GET .../search-urls/in-search/history` → `{history:[{date,value}]}` – число страниц в поиске.
- `GET .../search-urls/in-search/samples` → примеры страниц в поиске `{url, last_access, title}`.
- `GET .../search-urls/events/history` → `{indicators:{APPEARED_IN_SEARCH:[...],REMOVED_FROM_SEARCH:[...]}}`.
- `GET .../search-urls/events/samples` → какие именно URL появились/выпали + `excluded_url_status`.

## 5. Sitemaps (два неймспейса, разная пагинация)
- `GET .../sitemaps` – найденные роботом (read-only). Cursor: `from`+`parent_id`, `limit` def 10 max 100. → `{sitemaps:[{sitemap_id, sitemap_url, last_access_date, errors_count, urls_count, children_count, sources[], sitemap_type}]}`. sources: ROBOTS_TXT|WEBMASTER|INDEX_SITEMAP.
- `GET .../sitemaps/{sitemap_id}` – один.
- `GET .../user-added-sitemaps` – добавленные вручную. **offset**-пагинация, `limit` def 100 max 100.
- `POST .../user-added-sitemaps` body `{url}` → `201 {sitemap_id}`. Errors 400 INVALID_URL, 404 HOST_NOT_VERIFIED, 409 SITEMAP_ALREADY_ADDED.
- `DELETE .../user-added-sitemaps/{sitemap_id}` → 204.

## 6. Diagnostics
`GET .../diagnostics` → `{problems:{PROBLEM_TYPE:{severity, state, last_state_update}}}`.
**severity:** `FATAL|CRITICAL|POSSIBLE_PROBLEM|RECOMMENDATION`. **state:** `PRESENT|ABSENT|UNDEFINED`.
Типы (репрезентативно): NO_SITEMAPS, DISALLOWED_IN_ROBOTS, DNS_ERROR, MAIN_PAGE_ERROR, THREATS, SLOW_AVG_RESPONSE_TIME, SSL_CERTIFICATE_ERROR, ERROR_IN_ROBOTS_TXT, NO_ROBOTS_TXT, NOT_MOBILE_FRIENDLY. Счётчики по severity – в /summary.

## 7. Recrawl / переобход
- `GET .../recrawl/quota` → `{daily_quota, quota_remainder}` (динамическая per-host, текущее значение – в ответе `quota`).
- `POST .../recrawl/queue` body `{url}` → `202 {task_id, quota_remainder}`. Errors 409 URL_ALREADY_ADDED, 429 QUOTA_EXCEEDED.
- `GET .../recrawl/queue?offset=&limit=&date_from=&date_to=` → история задач.
- `GET .../recrawl/queue/{task_id}` → `{state: IN_PROGRESS|DONE|FAILED}`.

## 8. Links
- `GET .../links/external/history?indicator=LINKS_TOTAL_COUNT` (**indicator REQUIRED**) → `{indicators:{LINKS_TOTAL_COUNT:[{date,value(string!)}]}}`.
- `GET .../links/external/samples?offset=&limit=` (1–100, def 10) → `{count, links:[{source_url, destination_url, discovery_date, source_last_access_date}]}`.
- `GET .../links/internal/broken/history` → `{indicators:{SITE_ERROR:[...],DISALLOWED_BY_USER:[...],UNSUPPORTED_BY_ROBOT:[...]}}` (value int).
- `GET .../links/internal/broken/samples?offset=&limit=&indicator=` → битые внутренние ссылки чинить.
NB: value type – string в external, int в internal. Парсить устойчиво.

## 9. Important URLs monitoring
- `GET .../important-urls` → `{urls:[{url, change_indicators[], indexing_status{status,http_code,access_date}, search_status{title,description,searchable,...}}]}`. change_indicators: INDEXING_HTTP_CODE|SEARCH_STATUS|TITLE|DESCRIPTION. Мониторить ключевые лендинги (дрейф title/description, выпал из поиска).
- `GET .../important-urls/history?url=<encoded>` → таймлайн.

## 10. Turbo/Regions/Mirrors/Original-texts – статус
Turbo = отдельный API (yandex.com/dev/turbo), в Вебмастере только `/turbo/uploadAddress`; Турбо свёрнут ~2024. Regions/Mirrors – теперь UI-only (нет в v4; main_mirror всё ещё в host-объектах). Original-texts – закрыт Яндексом ~09.2020.

## 11. Ошибки / лимиты / гочи
Ключевые коды: 403 INVALID_OAUTH_TOKEN / INVALID_USER_ID / ACCESS_FORBIDDEN; 404 HOST_NOT_LOADED (свежий хост, грузится часы-сутки) / HOST_NOT_VERIFIED / HOST_NOT_INDEXED / HOST_NOT_FOUND / RESOURCE_NOT_FOUND / QUERY_ID_NOT_FOUND / TASK_NOT_FOUND; 409 URL_ALREADY_ADDED / SITEMAP_ALREADY_ADDED; 429 QUOTA_EXCEEDED / TOO_MANY_REQUESTS_ERROR (бэкофф).
Гочи: host_id `protocol:host:port` URL-энкодить; **HOST_NOT_LOADED** на /summary,/search-queries,/indexing пока host_data_status≠OK – поллить `GET /hosts/{hid}`; `order_by` обязателен и только shows/clicks; `query_indicator`/`indicator` повторяемые; recrawl пути `/recrawl/queue` и `/recrawl/quota`; индекс/исключ. счётчики – в /summary; нет опубликованного RPS-лимита (бэкофф на 429).

## 12. Рецепты
- ТОП запросов: `webmaster.py queries --host example.com --indicator TOTAL_SHOWS --indicator TOTAL_CLICKS --indicator AVG_SHOW_POSITION --days 28 --limit 500`
- «Почти топ» (поз. 4–10): тот же → фильтр AVG_SHOW_POSITION 4..10, сорт по TOTAL_SHOWS.
- Индекс/ИКС/исключённые: `webmaster.py summary --host example.com`.
- Ошибки обхода: `webmaster.py indexing --host example.com` + `diagnostics`.
- Загнать страницу в индекс: `webmaster.py recrawl --host example.com --url <URL>`.
- Добавить карту: `webmaster.py sitemaps --host example.com --add https://example.com/sitemap.xml`.
- Битые внутренние ссылки: `webmaster.py raw --method GET --path /user/<uid>/hosts/<hid>/links/internal/broken/samples?limit=100`.
