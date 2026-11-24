# Yandex Metrika API – reference

Source: official docs `yandex.ru/dev/metrika`. Host: `https://api-metrika.yandex.net`.
Auth header on EVERY request: `Authorization: OAuth <token>`.

## Dates
Absolute `YYYY-MM-DD`; relative `today`, `yesterday`, `NdaysAgo` (e.g. `30daysAgo`).

## Quotas (HTTP 429 on excess)
- 30 req/s per IP (general); Logs API 10 req/s.
- 5000 req/day per user; 3 parallel requests per account.
- Reporting: 200 req / 5 min per user.
- Stat API: max 20 metrics, 10 dimensions, `limit` ≤ 100000.
- Sampling: check `sampled` / `sample_share` in the response; raise with `accuracy=full`.

## Счётчики
Счётчик – числовой id. Сайтов может быть несколько, у каждого свой счётчик (в отличие от одной «property» в GA4). Список доступных счётчиков и их цели: `scripts/metrika_check.py`. Счётчик по умолчанию – переменная `METRIKA_COUNTER_ID`, либо флаг `--counter`.

---

## 1. Management API (`/management/v1/...`)

| Op | Method | Path |
|---|---|---|
| List counters | GET | `/management/v1/counters` (params: `counter_ids`, `per_page`, `status`, `sort`, `search_string`) |
| Get counter | GET | `/management/v1/counter/{id}` (`field=goals,filters,grants,...`) |
| List goals | GET | `/management/v1/counter/{id}/goals` (`useDeleted`) |
| Create goal | POST | `/management/v1/counter/{id}/goals` (needs `metrika:write`) |
| Update/delete goal | PUT/DELETE | `/management/v1/counter/{id}/goal/{goalId}` |
| Segments | GET/POST | `/management/v1/counter/{id}/apilab/segments` |
| Filters | GET/POST | `/management/v1/counter/{id}/filters` |

### Goal types
`action, chat, email, file, messenger, number, payment_system, phone, search, social, step, url, visit_duration`.

### Create-goal body (wrapped in `goal`)
URL goal – `conditions[].type ∈ {exact, contain, start, regexp}`, `url` = path pattern:
```json
{ "goal": { "name": "Purchase", "type": "url", "default_price": 50,
  "conditions": [ { "type": "contain", "url": "/thank-you" } ] } }
```
Action goal (JS event via `ym(id,'reachGoal','<id>')`) – `type = "action"`, `conditions[].type = "exact"` (значение `"action"` API отклоняет с HTTP 400), `url` = event id:
```json
{ "goal": { "name": "Form Submit", "type": "action",
  "conditions": [ { "type": "exact", "url": "form_submit" } ] } }
```
Optional: `is_favorite`, `is_retargeting`, `depth` (depth goal), `duration` (visit_duration sec), `steps` (≤5 for step), `flag` (`basket`/`order`, Я.Маркет only).

---

## 2. Reporting / Stat API (`GET /stat/v1/data`)

Params: `ids` (counter id(s), comma-sep), `metrics` (≤20), `dimensions` (≤10), `date1`,
`date2`, `filters`, `sort` (`-` prefix = desc), `limit` (≤100000), `offset`, `accuracy`,
`timezone`, `include_undefined`, `preset`, `lang`, `pretty`.

Response: `{query, data:[{dimensions:[{name}], metrics:[...]}], totals, total_rows, sampled, sample_share, ...}`.

### Metrics (`ym:s:` = sessions/visits) – verified
`ym:s:visits`, `ym:s:users`, `ym:s:pageviews`, `ym:s:bounceRate`, `ym:s:pageDepth`,
`ym:s:avgVisitDurationSeconds`, `ym:s:percentNewVisitors`,
`ym:s:goal<GID>reaches`, `ym:s:goal<GID>conversionRate`, `ym:s:goal<GID>users`,
`ym:s:sumGoalReachesAny`. (`<GID>` = numeric goal id, e.g. `ym:s:goal142536reaches`.)

### Dimensions (`ym:s:`)
Verified: `ym:s:trafficSource`, `ym:s:lastTrafficSource`, `ym:s:UTMSource`,
`ym:s:UTMMedium`, `ym:s:UTMCampaign`, `ym:s:UTMContent`, `ym:s:UTMTerm`,
`ym:s:referer`, `ym:s:searchEngine`, `ym:s:advEngine`.
Canonical but VERIFY-LIVE (docs ref 404'd this session – confirm via a live query or the dimensions reference before relying): `ym:s:startURL` (landing – there is NO `landingPage`), `ym:s:endURL`, `ym:s:date`, `ym:s:dateTime`, `ym:s:deviceCategory`, `ym:s:operatingSystem`, `ym:s:browser`, `ym:s:regionCountry`, `ym:s:regionCity`, `ym:s:regionArea`, `ym:s:gender`, `ym:s:age`.

### Ready reports (marketing question → params). `<C>`=counter, `<GID>`=goal id.
| Вопрос | Params |
|---|---|
| Визиты/юзеры по дням | `metrics=ym:s:visits,ym:s:users&dimensions=ym:s:date&date1=30daysAgo&sort=ym:s:date` |
| Источники трафика + отказы | `metrics=ym:s:visits,ym:s:bounceRate&dimensions=ym:s:trafficSource&sort=-ym:s:visits` |
| UTM-кампании + конверсия | `metrics=ym:s:visits,ym:s:goal<GID>reaches,ym:s:goal<GID>conversionRate&dimensions=ym:s:UTMCampaign,ym:s:UTMSource&sort=-ym:s:goal<GID>reaches&limit=50` |
| Landing pages | `metrics=ym:s:visits,ym:s:bounceRate,ym:s:avgVisitDurationSeconds&dimensions=ym:s:startURL&sort=-ym:s:visits&limit=50` |
| География | `metrics=ym:s:visits&dimensions=ym:s:regionCountry,ym:s:regionCity&sort=-ym:s:visits&limit=100` |
| Устройства | `metrics=ym:s:visits,ym:s:bounceRate&dimensions=ym:s:deviceCategory&sort=-ym:s:visits` |
| Все цели по дням | `metrics=ym:s:visits,ym:s:sumGoalReachesAny&dimensions=ym:s:date&sort=ym:s:date` |
| UTM-source × landing (cpc) | `metrics=ym:s:visits,ym:s:goal<GID>reaches&dimensions=ym:s:UTMSource,ym:s:startURL&filters=ym:s:UTMMedium=='cpc'&sort=-ym:s:visits` |

`metrika_report.py` принимает голые имена `ym:s:...` в `--metrics`/`--dimensions`.

---

## 3. Logs API (`/management/v1/counter/{id}/logrequests...`)
Асинхронный экспорт СЫРЫХ hit-level данных (`source=visits` или `hits`) – то, чего нет в агрегированном Stat API. Поток: `POST .../logrequests` (создать, `date1/date2/fields`) → `GET .../logrequests/{rid}` (ждать статус `processed`) → `GET .../logrequests/{rid}/part/{n}` (скачать части) → `POST .../logrequests/{rid}/clean`. Статусы: created → processing → processed (+ canceled/failed). 10 req/s.

---

## Дочитываемость (пример цели-события)
Если на страницах статей стоит скрипт, который отправляет события `ym(<COUNTER_ID>, 'reachGoal', 'scroll_25' | 'scroll_50' | 'scroll_75' | 'scroll_100')`, под каждое событие можно создать цель типа `action`:

```bash
python3 scripts/metrika_goal.py --counter <COUNTER_ID> --name "Дочитал 75%" --type action --url scroll_75 --commit
```

Процент дочитавших по страницам – конверсия этой цели в разрезе посадочных:

```bash
python3 scripts/metrika_report.py --counter <COUNTER_ID> \
    --metrics ym:s:visits,ym:s:goal<GOAL_ID>reaches,ym:s:goal<GOAL_ID>conversionRate \
    --dimensions ym:s:startURL --sort=-ym:s:visits
```

`<GOAL_ID>` берётся из вывода `metrika_check.py`.
