"""Копирует найденные в Discogs альбомы и издания из одной базы в другую (например, из локальной dev-базы
в Supabase), чтобы не сопоставлять уже известные штрихкоды заново. Существующие строки не трогает.

    .venv/bin/python scripts/copy_catalog.py --source .env --target .env.production
"""

import argparse
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

ROOT = Path(__file__).resolve().parent.parent


def database_url(env_file: str) -> str:
    for line in (ROOT / env_file).read_text(encoding="utf-8").splitlines():
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit(f"в {env_file} нет DATABASE_URL")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=".env")
    parser.add_argument("--target", default=".env.production")
    args = parser.parse_args()

    with psycopg.connect(database_url(args.source)) as src, \
         psycopg.connect(database_url(args.target), prepare_threshold=None) as dst:
        masters = src.execute(
            """select id, title, artist_display, year, genres, styles, cover_url, cover_thumb, tracklist,
                      discogs_uri, fetched_at from master"""
        ).fetchall()
        releases = src.execute(
            """select id, master_id, title, year, country, label, catno, format_qty, format_desc, barcode_keys,
                      fetched_at from release"""
        ).fetchall()
        with dst.cursor() as cur:
            cur.executemany(
                """insert into master (id, title, artist_display, year, genres, styles, cover_url, cover_thumb,
                                       tracklist, discogs_uri, fetched_at)
                   values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) on conflict (id) do nothing""",
                [(*m[:8], Jsonb(m[8]) if m[8] is not None else None, *m[9:]) for m in masters],
            )
            cur.executemany(
                """insert into release (id, master_id, title, year, country, label, catno, format_qty, format_desc,
                                        barcode_keys, fetched_at)
                   values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) on conflict (id) do nothing""",
                releases,
            )
        dst.commit()
        total_m = dst.execute("select count(*) from master").fetchone()[0]
        total_r = dst.execute("select count(*) from release").fetchone()[0]
    print(f"скопировано из {args.source}: альбомов {len(masters)}, изданий {len(releases)}; "
          f"в {args.target} теперь альбомов {total_m}, изданий {total_r}")


if __name__ == "__main__":
    main()
