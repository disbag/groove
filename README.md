# Groove

**Groove** — некоммерческий агрегатор цен на **новые** виниловые пластинки в российских магазинах.
Сайт: <https://disbag.github.io/groove/> · репозиторий: `disbag/groove`.
Каждую ночь конвейер собирает цены, сопоставляет позиции с Discogs по штрихкоду и публикует статический сайт.

```
GitHub Actions (cron 03:30 МСК)
  └─ python -m pipeline nightly
       ├─ scrape  — адаптеры магазинов → таблица offer (только текущее состояние)
       ├─ match   — Discogs API: штрихкод → издание → альбом (master)
       └─ export  — web/public/data/*.json
  └─ npm run build → GitHub Pages
Supabase (PostgreSQL) — хранилище конвейера; сайт к базе не обращается
```

## Магазины

| Код | Магазин | Источник данных |
|---|---|---|
| `stoprobot` | stoprobot.ru | InSales JSON `/collection/vinilovye-plastinki.json` |
| `korobka` | korobkavinyla.ru | Tilda Store API (раздел «Винил», только в наличии) |
| `pult` | pult.ru | JSON `catalogListParams.products` в HTML листинга |

Новый магазин — это модуль в `pipeline/adapters/` с `SHOP` и `fetch(http) -> list[Offer]`, добавленный в `ADAPTERS`.
Магазин можно временно выключить в базе: `update shop set is_active = false where code = '...'`.

## Настройка (один раз)

1. **Supabase**: создать проект → *Connect* → *Session pooler* → скопировать строку подключения
   (`postgresql://postgres.<ref>:<пароль>@aws-...pooler.supabase.com:5432/postgres`).
   Прямое подключение `db.<ref>.supabase.co` работает только по IPv6, а раннеры GitHub его не поддерживают.
2. **Discogs**: <https://www.discogs.com/settings/developers> → *Generate new token*.
3. **GitHub** → *Settings* → *Secrets and variables* → *Actions*: секреты `DATABASE_URL` и `DISCOGS_TOKEN`.
4. **GitHub** → *Settings* → *Pages* → *Source*: **GitHub Actions**.
5. *Actions* → *Nightly update* → *Run workflow*. Первое сопоставление ~8,5 тыс. штрихкодов занимает ~5 часов;
   за ночь конвейер обрабатывает сколько успеет (`--budget-minutes`, по умолчанию 240) и продолжает в следующую ночь.

## Локальный сбор (Пульт)

Пульт отвечает 403 серверам GitHub, поэтому в Actions он пропускается (`GROOVE_SHOPS_EXCLUDE=pult`)
и собирается с домашнего компьютера в ту же базу Supabase:

```bash
# app/.env.production — строка Session pooler (не попадает в git)
read -rs "DB?Supabase Session pooler URL: " && printf 'DATABASE_URL=%s\n' "$DB" > .env.production \
  && grep '^DISCOGS_TOKEN=' .env >> .env.production && chmod 600 .env.production
scripts/local_run.sh              # сбор Пульта + сопоставление; лог: ~/Library/Logs/groove-local.log
scripts/install_launchd.sh        # ежедневно в 02:30, до ночного прогона на GitHub; --remove — удалить
.venv/bin/python scripts/copy_catalog.py --source .env --target .env.production   # перенести найденное локально
```

## Локальная разработка

```bash
python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python scripts/dev_db.py          # локальный Postgres; строку подключения — в app/.env
echo "DISCOGS_TOKEN=..." >> .env            # .env в .gitignore
.venv/bin/python -m pipeline migrate
.venv/bin/python -m pipeline scrape --shops stoprobot,korobka
.venv/bin/python -m pipeline match --budget-minutes 10
.venv/bin/python -m pipeline export
cd web && npm install && npm run dev        # http://localhost:5173
.venv/bin/python -m pytest -q tests
```

## Правила

- **Магазины**: свой User-Agent с адресом сайта, не чаще 1 запроса в секунду на магазин, только публичные страницы каталога.
- **Discogs** (API Terms of Use): храним только CC0-поля (названия, год, форматы, жанры, штрихкоды, треклисты),
  обложки подгружаются с `i.discogs.com`; на сайте есть «Data provided by Discogs» со ссылкой и отказ от аффилированности.
  Проект некоммерческий — при монетизации условия Discogs нужно пересмотреть.
- **Персональные данные** не собираются: регистрации нет, избранное хранится в `localStorage` браузера.
