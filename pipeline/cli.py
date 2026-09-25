"""Точка входа: python -m pipeline <команда>."""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import config, db, export, match, scrape
from .discogs import Discogs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m pipeline", description="Конвейер цен на винил")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("migrate", help="создать/обновить схему БД")
    p_scrape = sub.add_parser("scrape", help="собрать цены из магазинов")
    p_scrape.add_argument("--shops", help="коды магазинов через запятую (по умолчанию все)")
    p_match = sub.add_parser("match", help="сопоставить новые позиции с Discogs")
    p_match.add_argument("--budget-minutes", type=float, default=240)
    p_match.add_argument("--limit", type=int)
    p_refresh = sub.add_parser("refresh", help="обновить данные альбомов (ссылки на обложки) по кругу")
    p_refresh.add_argument("--limit", type=int, default=500)
    p_refresh.add_argument("--budget-minutes", type=float, default=15)
    p_export = sub.add_parser("export", help="выгрузить статические JSON для сайта")
    p_export.add_argument("--out", type=Path, default=config.DEFAULT_EXPORT_DIR)
    p_nightly = sub.add_parser("nightly", help="migrate → scrape → match → refresh → export → status")
    p_nightly.add_argument("--budget-minutes", type=float, default=240)
    p_nightly.add_argument("--out", type=Path, default=config.DEFAULT_EXPORT_DIR)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    conn = db.connect()

    if args.command == "migrate":
        db.migrate(conn)
    elif args.command == "scrape":
        scrape.run(conn, args.shops.split(",") if args.shops else None)
    elif args.command == "match":
        match.run(conn, Discogs(), args.budget_minutes, args.limit)
    elif args.command == "refresh":
        match.refresh(conn, Discogs(), args.limit, args.budget_minutes)
    elif args.command == "export":
        print(export.run(conn, args.out))
    elif args.command == "nightly":
        return _nightly(conn, args)
    return 0


def _nightly(conn, args) -> int:
    status = {"started_at": _now()}
    db.migrate(conn)
    status["scrape"] = scrape.run(conn)
    discogs = Discogs()  # один клиент на прогон — общий учёт лимита запросов
    status["match"] = match.run(conn, discogs, args.budget_minutes)
    status["refresh"] = match.refresh(conn, discogs, limit=500, budget_minutes=15)
    status["export"] = export.run(conn, args.out)
    status["finished_at"] = _now()
    config.STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.STATUS_PATH.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    ok_shops = [s for s in status["scrape"] if s["status"] in ("ok", "partial")]
    return 0 if ok_shops and status["export"]["albums"] > 0 else 1


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


if __name__ == "__main__":
    sys.exit(main())
