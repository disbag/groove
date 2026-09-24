"""Работа с PostgreSQL: схема, магазины, журнал прогонов, запись предложений."""

from datetime import datetime

import psycopg
from psycopg.rows import dict_row

from . import config
from .models import Offer, Shop


def connect() -> psycopg.Connection:
    if not config.DATABASE_URL:
        raise SystemExit("DATABASE_URL не задан (переменная окружения или app/.env)")
    # prepare_threshold=None — совместимость с пулером Supabase (Supavisor) в режиме transaction.
    return psycopg.connect(config.DATABASE_URL, autocommit=True, row_factory=dict_row, prepare_threshold=None)


def migrate(conn: psycopg.Connection) -> None:
    conn.execute(config.SCHEMA_PATH.read_text(encoding="utf-8"))


def ensure_shop(conn: psycopg.Connection, shop: Shop) -> int:
    row = conn.execute(
        """insert into shop (code, name, base_url, adapter) values (%s, %s, %s, %s)
           on conflict (code) do update set name = excluded.name, base_url = excluded.base_url,
                                            adapter = excluded.adapter
           returning id, is_active""",
        (shop.code, shop.name, shop.base_url, shop.adapter),
    ).fetchone()
    return row["id"]


def shop_is_active(conn: psycopg.Connection, shop_id: int) -> bool:
    return conn.execute("select is_active from shop where id = %s", (shop_id,)).fetchone()["is_active"]


def start_run(conn: psycopg.Connection, shop_id: int) -> tuple[int, datetime]:
    row = conn.execute(
        "insert into scrape_run (shop_id, status) values (%s, 'running') returning id, started_at", (shop_id,)
    ).fetchone()
    return row["id"], row["started_at"]


def finish_run(conn, run_id: int, status: str, offers_seen: int = 0, offers_changed: int = 0,
               error: str | None = None) -> None:
    conn.execute(
        """update scrape_run set finished_at = now(), status = %s, offers_seen = %s, offers_changed = %s, error = %s
           where id = %s""",
        (status, offers_seen, offers_changed, error, run_id),
    )


def previous_seen(conn, shop_id: int) -> int | None:
    row = conn.execute(
        """select offers_seen from scrape_run where shop_id = %s and status = 'ok'
           order by started_at desc limit 1""",
        (shop_id,),
    ).fetchone()
    return row["offers_seen"] if row else None


_UPSERT = """
insert into offer (shop_id, external_id, url, raw_title, artist_hint, album_hint, barcode, price, in_stock,
                   color, color_raw, format_qty, image_url)
values (%(shop_id)s, %(external_id)s, %(url)s, %(raw_title)s, %(artist_hint)s, %(album_hint)s, %(barcode)s,
        %(price)s, %(in_stock)s, %(color)s, %(color_raw)s, %(format_qty)s, %(image_url)s)
on conflict (shop_id, external_id) do update set
  url = excluded.url,
  raw_title = excluded.raw_title,
  artist_hint = excluded.artist_hint,
  album_hint = excluded.album_hint,
  color = excluded.color,
  color_raw = excluded.color_raw,
  format_qty = excluded.format_qty,
  image_url = excluded.image_url,
  price = excluded.price,
  in_stock = excluded.in_stock,
  barcode = excluded.barcode,
  -- сменился штрихкод — сопоставляем заново
  match_status = case when offer.barcode is distinct from excluded.barcode then 'pending' else offer.match_status end,
  release_id = case when offer.barcode is distinct from excluded.barcode then null else offer.release_id end,
  master_id = case when offer.barcode is distinct from excluded.barcode then null else offer.master_id end,
  updated_at = case when offer.price is distinct from excluded.price or offer.in_stock is distinct from excluded.in_stock
                    then now() else offer.updated_at end,
  missed_runs = 0,
  last_seen_at = now()
"""


def upsert_offers(conn: psycopg.Connection, shop_id: int, offers: list[Offer]) -> int:
    """Записывает позиции и возвращает число новых или изменившихся (цена, наличие)."""
    existing = {
        row["external_id"]: (row["price"], row["in_stock"])
        for row in conn.execute("select external_id, price, in_stock from offer where shop_id = %s", (shop_id,))
    }
    unique = {offer.external_id: offer for offer in offers}  # магазины иногда дублируют товар на двух страницах
    changed = sum(1 for o in unique.values() if existing.get(o.external_id) != (o.price, o.in_stock))
    rows = [{**offer.__dict__, "shop_id": shop_id} for offer in unique.values()]
    with conn.cursor() as cur:
        cur.executemany(_UPSERT, rows)
    return changed


def mark_missing(conn: psycopg.Connection, shop_id: int, run_started_at: datetime) -> int:
    """Позиции, которых не было в этом прогоне: считаем пропуски и снимаем с наличия после N пропусков."""
    conn.execute(
        "update offer set missed_runs = missed_runs + 1 where shop_id = %s and last_seen_at < %s",
        (shop_id, run_started_at),
    )
    return conn.execute(
        """update offer set in_stock = false, updated_at = now()
           where shop_id = %s and in_stock and missed_runs >= %s""",
        (shop_id, config.MISSED_RUNS_TO_OUT_OF_STOCK),
    ).rowcount


def purge_stale(conn: psycopg.Connection) -> int:
    return conn.execute(
        "delete from offer where last_seen_at < now() - make_interval(days => %s)", (config.PURGE_AFTER_DAYS,)
    ).rowcount
