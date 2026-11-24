---
name: yandex-webmaster
description: >-
  SEO-данные сайта через API Яндекс.Вебмастера: по каким поисковым запросам
  сайт показывается, позиции в выдаче, показы/клики/CTR из поиска, индексация
  (страницы в поиске, ошибки обхода), переобход страницы, sitemap, технические
  проблемы сайта для поиска, ИКС (SQI), внешние ссылки. Используй этот скилл,
  когда спрашивают про SEO, «по каким запросам нас находят», позиции,
  видимость в Яндексе, индексацию, «добавь sitemap», «отправь страницу на
  переобход» – даже если слово «Вебмастер» не произнесено. Yandex Webmaster
  API: search queries, positions, indexing, sitemaps, diagnostics, recrawl.
  Для поведения на сайте (визиты, источники, цели) – скилл yandex-metrika.
---

# Яндекс.Вебмастер – SEO-видимость сайта в поиске

Метрика показывает, что происходит на сайте. Вебмастер показывает, как сайт виден в поиске Яндекса: по каким запросам он появляется, на каких позициях, сколько показов и кликов, что в индексе, какие есть ошибки. Скилл – тонкая обёртка `scripts/webmaster.py` над API v4 (Python 3, стандартная библиотека).

## Когда запускать
- «что с SEO», «по каким запросам нас находят», «позиции в выдаче», «показы и клики из поиска»;
- «что с индексацией», «сколько страниц в поиске», «ошибки сайта», «переобход страницы»;
- «добавь sitemap», «видимость в Яндексе», «ИКС сайта».

## Настройка

| Переменная | Обязательна | Смысл |
|---|---|---|
| `YANDEX_OAUTH_TOKEN` | да | OAuth-токен с доступом к API Вебмастера (см. README, раздел про токен) |
| `WEBMASTER_HOST` | нет | сайт по умолчанию: домен (`example.com`), URL или полный host_id (`https:example.com:443`). Вместо неё можно передавать `--host` |
| `YANDEX_ENV_FILE` | нет | путь к файлу `KEY=VALUE` (по умолчанию `./.env`) |

Сайт должен быть добавлен и подтверждён в Вебмастере под тем же аккаунтом, что выпустил токен. `user_id` и `host_id` скрипт определяет сам. Токен не выводить в чат и не коммитить.

## Инструмент: `scripts/webmaster.py`

```bash
python3 scripts/webmaster.py hosts                                   # сайты аккаунта + статус подтверждения
python3 scripts/webmaster.py queries --host example.com \
    --indicator TOTAL_SHOWS --indicator TOTAL_CLICKS --indicator AVG_SHOW_POSITION \
    --days 28 --limit 50                                             # главный отчёт: топ запросов
python3 scripts/webmaster.py summary --host example.com              # ИКС (SQI), число проблем
python3 scripts/webmaster.py indexing --host example.com             # страницы в поиске, история
python3 scripts/webmaster.py diagnostics --host example.com          # проблемы сайта (severity/state)
python3 scripts/webmaster.py sitemaps --host example.com             # список; добавить: --add <url>
python3 scripts/webmaster.py recrawl --host example.com --url <URL>  # переобход URL (+ квота)
python3 scripts/webmaster.py links --host example.com                # внешние ссылки
python3 scripts/webmaster.py raw --method GET --path /user/          # произвольный вызов API
```

`--host` не нужен, если задана `WEBMASTER_HOST` (кроме `hosts` и `raw`, им сайт не нужен). Полный справочник эндпоинтов, параметров и перечислений – `references/webmaster-api.md`.

## Главный отчёт – поисковые запросы
`queries` читает `/search-queries/popular`. Индикаторы (`--indicator`, можно повторять):
- `TOTAL_SHOWS` – показы в выдаче;
- `TOTAL_CLICKS` – клики;
- `AVG_SHOW_POSITION` – средняя позиция показа (меньше – выше в выдаче);
- `AVG_CLICK_POSITION` – средняя позиция клика.

Сортировка – `--order-by TOTAL_SHOWS|TOTAL_CLICKS`; `--device ALL|DESKTOP|MOBILE|TABLET`; `--limit` до 500.

Рабочий приём: искать запросы с большим числом показов и позицией примерно 4–15 – «почти в топе». Их проще всего подтянуть контентом. API по позиции не фильтрует, фильтровать нужно на своей стороне.

## Задержка данных у нового сайта
Пока Яндекс загружает только что добавленный сайт, `summary`, `queries` и `indexing` отвечают `HOST_NOT_LOADED`; скрипт перехватывает это и печатает понятный статус. Загрузка занимает от нескольких часов до суток, данные по запросам накапливаются ещё несколько дней. Сразу работают `hosts`, `sitemaps`, `diagnostics`, `recrawl`, `links`.

## Как подавать результат
Сначала вывод (что чинить, что докрутить), потом таблица запросов. Цифры без округлений «на глаз», тире короткое «–», без эмодзи.
