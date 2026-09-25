"""Сбор цен: по очереди запускает адаптеры и записывает результат. Сбой одного магазина не валит остальные."""

import logging
import time

from . import config, db
from .adapters import ADAPTERS
from .http import PoliteSession

log = logging.getLogger(__name__)


def run(conn, shop_codes: list[str] | None = None) -> list[dict]:
    http = PoliteSession()
    summary = []
    for code, module in ADAPTERS.items():
        if shop_codes and code not in shop_codes:
            continue
        if not shop_codes and code in config.SHOPS_EXCLUDE:
            log.info("%s: пропущен (GROOVE_SHOPS_EXCLUDE)", code)
            continue
        shop_id = db.ensure_shop(conn, module.SHOP)
        if not db.shop_is_active(conn, shop_id):
            log.info("%s: магазин выключен (shop.is_active = false)", code)
            continue
        run_id, started_at = db.start_run(conn, shop_id)
        t0 = time.monotonic()
        result = {"shop": code, "status": "failed", "offers": 0, "changed": 0, "out_of_stock": 0}
        try:
            offers = module.fetch(http)
            previous = db.previous_seen(conn, shop_id)
            suspicious = previous is not None and len(offers) < previous * config.PARTIAL_RUN_RATIO
            changed = db.upsert_offers(conn, shop_id, offers)
            out_of_stock = 0
            if suspicious:
                # Похоже, магазин поменял вёрстку или адрес: не снимаем с наличия то, чего не увидели.
                status = "partial"
                log.warning("%s: %d позиций против %d в прошлый раз — прогон помечен partial", code, len(offers), previous)
            else:
                status = "ok"
                out_of_stock = db.mark_missing(conn, shop_id, started_at)
            db.finish_run(conn, run_id, status, len(offers), changed)
            result.update(status=status, offers=len(offers), changed=changed, out_of_stock=out_of_stock)
        except Exception as exc:  # noqa: BLE001 — любой сбой магазина фиксируем и идём дальше
            log.exception("%s: ошибка сбора", code)
            db.finish_run(conn, run_id, "failed", error=repr(exc)[:500])
            result["error"] = repr(exc)[:200]
        result["seconds"] = round(time.monotonic() - t0)
        log.info("%s: %s", code, result)
        summary.append(result)
    purged = db.purge_stale(conn)
    if purged:
        log.info("удалено устаревших позиций: %d", purged)
    return summary
