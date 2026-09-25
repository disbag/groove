"""Сопоставление позиций магазинов с Discogs: штрихкод → издание (release) → альбом (master).

Позиции без штрихкода ищем по «исполнитель + альбом» на уровне master с порогом похожести.
Из Discogs сохраняем только CC0-поля (названия, год, формат, жанры, штрихкоды, треклист) и ссылки на обложки.
"""

import logging
import re
import time
from collections import defaultdict
from difflib import SequenceMatcher

from psycopg.types.json import Jsonb

from .discogs import Discogs
from .normalize import barcode_key, clean_barcode, clean_discogs_name, detect_color, fold, title_key

log = logging.getLogger(__name__)
TEXT_MATCH_THRESHOLD = 0.82
MAX_RELEASES_PER_BARCODE = 10  # у популярных альбомов под одним штрихкодом бывают десятки репрессов


def run(conn, discogs: Discogs, budget_minutes: float = 240, limit: int | None = None) -> dict:
    deadline = time.monotonic() + budget_minutes * 60
    rows = conn.execute(
        """select id, barcode, raw_title, artist_hint, album_hint, color, format_qty
           from offer where match_status = 'pending' and in_stock
           order by barcode is null, id""" + (" limit %s" % int(limit) if limit else "")
    ).fetchall()
    by_key: dict[str, list[dict]] = defaultdict(list)
    no_barcode: list[dict] = []
    for row in rows:
        if row["barcode"]:
            by_key[barcode_key(row["barcode"])].append(row)
        else:
            no_barcode.append(row)

    _backfill_title_keys(conn)
    stats = defaultdict(int)
    for key, offers in by_key.items():
        if time.monotonic() > deadline:
            stats["deferred"] += len(offers)
            continue
        try:
            _match_barcode(conn, discogs, key, offers, stats)
        except Exception:  # noqa: BLE001 — сбой одной позиции не останавливает сопоставление
            log.exception("штрихкод %s: ошибка, позиция останется pending", key)
            stats["errors"] += 1
    for offer in no_barcode:
        if time.monotonic() > deadline:
            stats["deferred"] += 1
            continue
        try:
            _match_text(conn, discogs, offer, stats)
        except Exception:  # noqa: BLE001
            log.exception("позиция %s: ошибка, останется pending", offer["id"])
            stats["errors"] += 1
    stats["api_calls"] = discogs.calls
    log.info("сопоставление: %s", dict(stats))
    return dict(stats)


# ---------- по штрихкоду ----------

def _match_barcode(conn, discogs: Discogs, key: str, offers: list[dict], stats) -> None:
    candidates = _local_releases(conn, key)
    from_search = not candidates
    if from_search:
        results = discogs.search_barcode(offers[0]["barcode"])
        vinyl = [r for r in results if "Vinyl" in (r.get("format") or [])]
        # Discogs ищет штрихкод и как подстроку — оставляем только точные совпадения
        exact = [r for r in vinyl if key in {barcode_key(b) for b in _barcodes(r.get("barcode"))}]
        candidates = [_candidate(r) for r in (exact or vinyl)[:MAX_RELEASES_PER_BARCODE]]
    for offer in offers:
        best = max(candidates, key=lambda rel: _score(rel, offer)) if candidates else None
        if best is None or _album_coverage(offer, best["title"] or "") < 0.5:
            # Штрихкода нет в Discogs или он нашёлся внутри чужого издания (например, бокс-сета) —
            # пробуем найти альбом по названию.
            _match_text(conn, discogs, offer, stats)
            continue
        if from_search:
            # В базу пишем только выбранное издание: так на штрихкод уходит 1–2 запроса к API, а не 10
            _save_release_from_search(conn, discogs, best["result"])
            best["master_id"] = best["result"].get("master_id") or -best["id"]
        conn.execute(
            "update offer set release_id = %s, master_id = %s, match_status = 'barcode' where id = %s",
            (best["id"], best["master_id"], offer["id"]),
        )
        stats["barcode"] += 1


def _candidate(result: dict) -> dict:
    formats = result.get("formats") or [{}]
    desc = [*(result.get("format") or [])] + ([formats[0]["text"]] if formats[0].get("text") else [])
    return {
        "id": result["id"], "master_id": result.get("master_id") or -result["id"], "title": result.get("title"),
        "format_qty": _int(formats[0].get("qty")), "format_desc": desc, "result": result,
    }


def _barcodes(values) -> list[str]:
    out = []
    for value in values or []:
        digits = clean_barcode(value)
        if digits:
            out.append(digits)
    return out


def _local_releases(conn, key: str) -> list[dict]:
    return conn.execute(
        "select id, master_id, title, format_qty, format_desc from release where barcode_keys @> array[%s]", (key,)
    ).fetchall()


def _score(release: dict, offer: dict) -> float:
    """Выбор издания среди нескольких с одним штрихкодом: цвет и количество пластинок."""
    desc = " ".join(release.get("format_desc") or [])
    score = 0.0
    release_color = detect_color(desc)
    if release_color == offer["color"]:
        score += 2
    elif offer["color"] != "black" and release_color != "black":
        score += 1
    if offer["format_qty"] and release.get("format_qty") == offer["format_qty"]:
        score += 1
    return score + 3 * _album_coverage(offer, release.get("title") or "")


def _save_release_from_search(conn, discogs: Discogs, result: dict) -> None:
    release_id = result["id"]
    master_id = result.get("master_id") or 0
    if master_id <= 0:
        master_id = -release_id  # релиз без мастера — карточкой становится сам релиз
    _ensure_master(conn, discogs, master_id, release_id)
    formats = result.get("formats") or [{}]
    desc = [*(result.get("format") or [])]
    if formats[0].get("text"):
        desc.append(formats[0]["text"])
    title = result.get("title") or ""
    conn.execute(
        """insert into release (id, master_id, title, year, country, label, catno, format_qty, format_desc, barcode_keys)
           values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
           on conflict (id) do update set barcode_keys = excluded.barcode_keys, format_desc = excluded.format_desc,
                                          fetched_at = now()""",
        (
            release_id, master_id, title, _year(result.get("year")), result.get("country"),
            (result.get("label") or [None])[0], result.get("catno"),
            _int(formats[0].get("qty")), desc,
            sorted({barcode_key(b) for b in _barcodes(result.get("barcode"))}),
        ),
    )


# ---------- по названию ----------

def _match_text(conn, discogs: Discogs, offer: dict, stats) -> None:
    master_id = _local_master_by_text(conn, offer)
    if master_id:
        conn.execute("update offer set master_id = %s, match_status = 'text' where id = %s", (master_id, offer["id"]))
        stats["text_local"] += 1
        return
    query = _text_query(offer)
    # Ищем среди виниловых изданий: фильтр format=Vinyl у поиска по master теряет альбомы,
    # у которых главное издание — CD.
    results = discogs.search_vinyl_releases(query) if query else []
    best, best_ratio = None, 0.0
    for result in results[:10]:
        ratio = _similarity(query, (result.get("title") or "").replace(" - ", " "))
        if ratio > best_ratio:
            best, best_ratio = result, ratio
    if not best or best_ratio < TEXT_MATCH_THRESHOLD:
        _set_status(conn, offer["id"], "not_found")
        stats["not_found"] += 1
        return
    _save_release_from_search(conn, discogs, best)
    master_id = best.get("master_id") or -best["id"]
    conn.execute(
        "update offer set release_id = %s, master_id = %s, match_status = 'text' where id = %s",
        (best["id"], master_id, offer["id"]),
    )
    stats["text"] += 1


def _local_master_by_text(conn, offer: dict) -> int | None:
    """Альбом с тем же названием уже есть в базе и исполнитель похож — берём его без запроса к Discogs."""
    key = title_key(offer.get("album_hint"))
    if len(key) < 2:
        return None
    rows = conn.execute("select id, artist_display from master where title_key = %s", (key,)).fetchall()
    artist = (offer.get("artist_hint") or "").strip()
    if not rows:
        return None
    if not artist or artist.lower() in _COMPILATION_ARTISTS:
        return rows[0]["id"] if len(rows) == 1 and rows[0]["artist_display"].lower() in ("various", "various artists") else None
    best = max(rows, key=lambda r: _similarity(artist, r["artist_display"]))
    return best["id"] if _similarity(artist, best["artist_display"]) >= 0.85 else None


def _backfill_title_keys(conn) -> None:
    """Заполняет и пересчитывает master.title_key (например, после изменения правил нормализации)."""
    rows = conn.execute("select id, title, title_key from master").fetchall()
    stale = [(title_key(r["title"]), r["id"]) for r in rows if r["title_key"] != title_key(r["title"])]
    if stale:
        with conn.cursor() as cur:
            cur.executemany("update master set title_key = %s where id = %s", stale)


_COMPILATION_ARTISTS = {"ost", "v/a", "va", "сборник", "various", "various artists", "саундтрек"}


def _text_query(offer: dict) -> str:
    artist = (offer["artist_hint"] or "").strip()
    album = (offer["album_hint"] or "").strip()
    if artist.lower() in _COMPILATION_ARTISTS:
        artist = ""
    query = " ".join(x for x in (artist, album) if x) or offer["raw_title"]
    query = re.sub(r"\([^)]*\)|\|.*$", " ", query)
    return re.sub(r"\s+", " ", query).strip()


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"\w+", fold(text))) - _STOP_TOKENS


_STOP_TOKENS = {"the", "a", "lp", "vinyl", "and", "of", "black", "gram", "180", "edition", "limited", "coloured", "colored"}


def _album_coverage(offer: dict, release_title: str) -> float:
    """Какая доля слов названия альбома из магазина есть в названии издания Discogs."""
    album = offer.get("album_hint") or re.sub(r"\([^)]*\)", " ", offer.get("raw_title") or "")
    wanted = _tokens(album)
    if not wanted:
        return 1.0
    return len(wanted & _tokens(release_title)) / len(wanted)


def _similarity(a: str, b: str) -> float:
    norm = lambda s: " ".join(sorted(re.sub(r"[^\w\s]", " ", fold(s)).split()))  # noqa: E731
    return SequenceMatcher(None, norm(a), norm(b)).ratio()


# ---------- карточка альбома ----------

def _ensure_master(conn, discogs: Discogs, master_id: int, release_id: int | None) -> None:
    if conn.execute("select 1 from master where id = %s", (master_id,)).fetchone():
        return
    data = discogs.master(master_id) if master_id > 0 else discogs.release(-master_id)
    if not data:
        raise RuntimeError(f"Discogs не вернул {'master' if master_id > 0 else 'release'} {abs(master_id)}")
    _upsert_master(conn, master_id, data)


def refresh(conn, discogs: Discogs, limit: int = 500, budget_minutes: float = 15) -> dict:
    """Перечитывает данные альбомов по кругу, начиная с самых давно обновлённых.

    Ссылки на обложки у Discogs подписанные и со временем устаревают; заодно подтягиваются правки
    в названиях, жанрах и треклистах. Обновляем только альбомы, которые сейчас есть в каталоге.
    """
    deadline = time.monotonic() + budget_minutes * 60
    ids = [
        row["id"]
        for row in conn.execute(
            """select m.id from master m
               where m.fetched_at < now() - interval '7 days'
                 and exists (select 1 from offer o where o.master_id = m.id and o.in_stock)
               order by m.fetched_at limit %s""",
            (limit,),
        )
    ]
    stats = defaultdict(int)
    for master_id in ids:
        if time.monotonic() > deadline:
            stats["deferred"] += 1
            continue
        try:
            data = discogs.master(master_id) if master_id > 0 else discogs.release(-master_id)
        except Exception:  # noqa: BLE001
            log.exception("альбом %s: не удалось обновить", master_id)
            stats["errors"] += 1
            continue
        if not data:
            # Удалён или слит с другим на Discogs — оставляем прежние данные, но в очередь ставим в конец
            conn.execute("update master set fetched_at = now() where id = %s", (master_id,))
            stats["missing"] += 1
            continue
        _upsert_master(conn, master_id, data)
        stats["refreshed"] += 1
    log.info("обновление альбомов: %s", dict(stats))
    return dict(stats)


def master_values(master_id: int, data: dict) -> dict:
    """Поля таблицы master из ответа Discogs /masters/{id} или /releases/{id} (для релизов без мастера)."""
    artists = data.get("artists") or []
    artist_display = "".join(
        clean_discogs_name(a.get("name") or "") + (f" {a['join']} " if a.get("join") else "")
        for a in artists
    ).replace(" , ", ", ").strip() or "Various"
    images = data.get("images") or []
    primary = next((i for i in images if i.get("type") == "primary"), images[0] if images else {})
    tracklist = [
        {"p": t.get("position"), "t": t.get("title"), "d": t.get("duration")}
        for t in data.get("tracklist") or [] if t.get("type_", "track") == "track"
    ]
    uri = data.get("uri") or ""
    return {
        "id": master_id,
        "title": data.get("title") or "",
        "artist_display": artist_display,
        "year": _year(data.get("year")),
        "genres": data.get("genres") or [],
        "styles": data.get("styles") or [],
        "cover_url": primary.get("uri") or None,
        "cover_thumb": primary.get("uri150") or None,
        "tracklist": tracklist,
        "discogs_uri": uri if uri.startswith("http") else (f"https://www.discogs.com{uri}" if uri else None),
        "title_key": title_key(data.get("title")),
    }


def _upsert_master(conn, master_id: int, data: dict) -> None:
    values = master_values(master_id, data)
    values["tracklist"] = Jsonb(values["tracklist"])
    conn.execute(
        """insert into master (id, title, artist_display, year, genres, styles, cover_url, cover_thumb, tracklist,
                               discogs_uri, title_key)
           values (%(id)s, %(title)s, %(artist_display)s, %(year)s, %(genres)s, %(styles)s,
                   %(cover_url)s, %(cover_thumb)s, %(tracklist)s, %(discogs_uri)s, %(title_key)s)
           on conflict (id) do update set
             title = excluded.title, title_key = excluded.title_key, artist_display = excluded.artist_display,
             year = excluded.year,
             genres = excluded.genres, styles = excluded.styles, cover_url = excluded.cover_url,
             cover_thumb = excluded.cover_thumb, tracklist = excluded.tracklist,
             discogs_uri = excluded.discogs_uri, fetched_at = now()""",
        values,
    )


def _set_status(conn, offer_id: int, status: str) -> None:
    conn.execute("update offer set match_status = %s where id = %s", (status, offer_id))


def _year(value) -> int | None:
    year = _int(value)
    return year if year and 1900 <= year <= 2100 else None


def _int(value) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None
