-- Схема Groove MVP: только новый винил, только текущее состояние (без истории цен), без пользователей.
-- Скрипт идемпотентный: `python -m pipeline migrate` можно запускать при каждом прогоне.

create table if not exists shop (
  id smallserial primary key,
  code text unique not null,            -- 'stoprobot', 'korobka', 'pult', ...
  name text not null,
  base_url text not null,
  adapter text not null,                -- 'insales_json' | 'tilda_api' | 'pult_embedded_json' | ...
  is_active boolean not null default true
);

create table if not exists master (     -- карточка каталога (альбом); CC0-поля Discogs
  id integer primary key,               -- discogs master id; для релизов без мастера: -release_id
  title text not null,
  artist_display text not null,
  year smallint,
  genres text[] not null default '{}',  -- жанры Discogs (15 штук)
  styles text[] not null default '{}',
  cover_url text,                       -- i.discogs.com, 600px
  cover_thumb text,                     -- i.discogs.com, 150px
  tracklist jsonb,
  discogs_uri text,
  fetched_at timestamptz not null default now()
);

alter table master add column if not exists title_key text;  -- normalize.title_key(title), для поиска по названию
create index if not exists master_title_key_idx on master (title_key);
alter table master add column if not exists core_key text;   -- title_key без приписок: «Black Swan (OST)» → blackswan
create index if not exists master_core_key_idx on master (core_key);

create table if not exists release (    -- издание (прессинг)
  id integer primary key,               -- discogs release id
  master_id integer not null references master(id),
  title text,
  year smallint,
  country text,
  label text,
  catno text,
  format_qty smallint,                  -- количество пластинок
  format_desc text[],                   -- ['LP','Album','Reissue','Red']
  barcode_keys text[] not null default '{}',  -- штрихкоды без ведущих нулей
  fetched_at timestamptz not null default now()
);
create index if not exists release_barcode_keys_idx on release using gin (barcode_keys);

create table if not exists offer (      -- позиция в магазине: только текущее состояние
  id bigserial primary key,
  shop_id smallint not null references shop(id),
  external_id text not null,            -- id товара в магазине
  url text not null,
  raw_title text not null,
  artist_hint text,                     -- исполнитель/альбом из магазина — для текстового сопоставления
  album_hint text,
  barcode text,
  release_id integer references release(id),
  master_id integer references master(id),
  match_status text not null default 'pending', -- pending | barcode | text | manual | not_found | rejected
  price integer,                        -- ₽
  in_stock boolean not null,
  color text not null default 'black',  -- black | coloured | splatter | clear | picture
  color_raw text,                       -- исходный текст магазина
  format_qty smallint,
  image_url text,
  missed_runs smallint not null default 0,   -- сколько прогонов подряд позиции не было в выдаче
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (shop_id, external_id)
);
create index if not exists offer_master_instock_idx on offer(master_id) where in_stock;
create index if not exists offer_pending_idx on offer(match_status) where match_status = 'pending';

create table if not exists scrape_run ( -- журнал прогонов: контроль поломок парсеров
  id serial primary key,
  shop_id smallint references shop(id),
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  status text,                          -- running | ok | partial | failed
  pages int,
  offers_seen int,
  offers_changed int,
  error text
);

-- Предложения, которые показываем на сайте: в наличии, с ценой, магазин включён и его данные свежие.
-- Свежесть считаем относительно самого свежего магазина, а не текущего времени: если конвейер не запускался
-- несколько дней, сайт показывает последние данные, а не пустой каталог.
--   * магазин собирался успешно (ok/partial) не раньше чем за 3 дня до самого свежего магазина —
--     иначе он сломался или закрылся, и его цены уже не актуальны;
--   * позиция была в выдаче не раньше чем за 3 дня до последнего успешного прогона своего магазина —
--     прогоны partial не снимают с наличия то, чего не увидели, и без этого условия позиция висела бы до purge.
-- security_invoker: представление подчиняется правам вызывающего, а не владельца.
create or replace view live_offer with (security_invoker = true) as
with shop_success as (
  select shop_id, max(started_at) as last_success
  from scrape_run where status in ('ok', 'partial') group by shop_id
)
select o.id, o.shop_id, o.master_id, o.release_id, o.url, o.price, o.color, o.color_raw, o.format_qty,
       o.image_url, o.first_seen_at
from offer o
join shop s on s.id = o.shop_id and s.is_active
join shop_success r on r.shop_id = o.shop_id
where o.in_stock and o.price is not null
  and r.last_success > (select max(last_success) from shop_success) - interval '3 days'
  and o.last_seen_at > r.last_success - interval '3 days';

-- Одна строка на альбом, у которого есть хотя бы одно предложение на сайте.
create or replace view catalog_card with (security_invoker = true) as
select m.id, m.artist_display, m.title, m.year, m.genres, m.styles,
       m.cover_url, m.cover_thumb, m.discogs_uri,
       min(o.price)                   as min_price,
       count(*)::int                  as offers_in_stock,
       count(distinct o.shop_id)::int as shops_in_stock,
       bool_or(o.color <> 'black')    as has_coloured,
       min(o.first_seen_at)           as first_seen_at
from master m
join live_offer o on o.master_id = m.id
group by m.id;

-- Supabase открывает схему public через REST API (PostgREST). Сайт к базе не обращается, поэтому
-- включаем RLS без политик: роли anon/authenticated не видят ничего, конвейер работает ролью postgres.
alter table shop enable row level security;
alter table master enable row level security;
alter table release enable row level security;
alter table offer enable row level security;
alter table scrape_run enable row level security;
