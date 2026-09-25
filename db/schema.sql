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

-- Одна строка на альбом, у которого есть хотя бы одно предложение в наличии.
create or replace view catalog_card as
select m.id, m.artist_display, m.title, m.year, m.genres, m.styles,
       m.cover_url, m.cover_thumb, m.discogs_uri,
       min(o.price)                   as min_price,
       count(*)::int                  as offers_in_stock,
       count(distinct o.shop_id)::int as shops_in_stock,
       bool_or(o.color <> 'black')    as has_coloured,
       min(o.first_seen_at)           as first_seen_at
from master m
join offer o on o.master_id = m.id and o.in_stock and o.price is not null
group by m.id;
