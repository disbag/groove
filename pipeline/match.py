"""Сопоставление позиций магазинов с Discogs: штрихкод → издание (release) → альбом (master).

Позиции без штрихкода ищем по «исполнитель + альбом» на уровне master с порогом похожести.
Из Discogs сохраняем только CC0-поля (названия, год, формат, жанры, штрихкоды, треклист) и ссылки на обложки.
"""

import logging
import re
import time
from collections import defaultdict
from psycopg.types.json import Jsonb

from . import textmatch
from .discogs import Discogs
from .normalize import barcode_key, clean_barcode, clean_discogs_name, detect_color, detect_qty, title_key, unescape

log = logging.getLogger(__name__)
MAX_RELEASES_PER_BARCODE = 10  # у популярных альбомов под одним штрихкодом бывают десятки репрессов


def run(conn, discogs: Discogs, budget_minutes: float = 240, limit: int | None = None,
        retry_not_found: bool = False) -> dict:
    deadline = time.monotonic() + budget_minutes * 60
    if retry_not_found:
        # после улучшения алгоритма — ещё раз попробовать то, что раньше не нашлось
        requeued = conn.execute(
            "update offer set match_status = 'pending' where match_status = 'not_found' and in_stock"
        ).rowcount
        log.info("повторная проверка ненайденных: %d", requeued)
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
    artist, album = _hints(offer)
    subtitle = _subtitle(offer, album)
    local = _local_master_by_text(conn, artist, album, subtitle)
    # Без подзаголовка в скобках альбом из базы годится сразу. С подзаголовком — только если он есть в названии:
    # иначе «Madame X (Music From The Theater Experience)» осел бы на студийном «Madame X», уже лежащем в базе.
    if local and (not subtitle or local[2]):
        _set_text_match(conn, offer["id"], local[1], None)
        stats["text_local"] += 1
        return
    if not album:
        _set_status(conn, offer["id"], "not_found")
        stats["not_found"] += 1
        return
    search_artist = None if textmatch.is_compilation(artist) else artist
    fallback = None
    # 1) среди виниловых изданий — так сразу известно конкретное издание; сначала вместе с подзаголовком
    for query_album in ([f"{album} {subtitle}"] if subtitle else []) + [album]:
        query = " ".join(x for x in (search_artist, query_album) if x)
        best = _best(artist, album, discogs.search_vinyl_releases(query), subtitle)
        if best and (not subtitle or best[1]):
            return _take_release(conn, discogs, offer["id"], best[0], stats)
        fallback = fallback or best
    if local:  # альбом из базы без подзаголовка лучше такого же из поиска: на него не нужен запрос
        _set_text_match(conn, offer["id"], local[1], None)
        stats["text_local"] += 1
        return
    if fallback:
        return _take_release(conn, discogs, offer["id"], fallback[0], stats)
    # 2) альбом по полям без фильтра формата: винил мог ещё не попасть в Discogs, а карточка у нас — альбом
    best = _best(artist, album, discogs.search_master_fields(search_artist, album), subtitle)
    if best:
        _ensure_master(conn, discogs, best[0]["id"], None)
        _set_text_match(conn, offer["id"], best[0]["id"], None)
        stats["text_master"] += 1
        return
    _set_status(conn, offer["id"], "not_found")
    stats["not_found"] += 1


def _take_release(conn, discogs: Discogs, offer_id: int, result: dict, stats) -> None:
    _save_release_from_search(conn, discogs, result)
    _set_text_match(conn, offer_id, result.get("master_id") or -result["id"], result["id"])
    stats["text"] += 1


def _set_text_match(conn, offer_id: int, master_id: int, release_id: int | None) -> None:
    conn.execute(
        "update offer set master_id = %s, release_id = %s, match_status = 'text' where id = %s",
        (master_id, release_id, offer_id),
    )


# Скобки с описанием издания, а не частью названия: «(LP)», «(Red Vinyl)», «(Deluxe Edition)», «(180g)»
_EDITION_NOTE = re.compile(
    r"\b(lp|ep|vinyl|винил\w*|vinile|пластинк\w*|edition|издание|remaster\w*|deluxe|anniversary|anniversaire|reissue"
    r"|limited|box|gatefold|rpm|\d+\s*(g|gr|gram)|mono|stereo|exclusive|press\w*|import|bonus|expanded|picture"
    r"|splatter|marble|clear|transparent|translucent|\d{4}|rsd|record store day|signed|автограф\w*|афтограф\w*"
    r"|подпис\w*|вложени\w*|экземпляр\w*|cd|dvd|blu-?ray|single|сингл|\d+\s*(\"|″|''|&quot;|inch|-inch)|series"
    r"|half[- ]?speed|cover|artwork|numbered|mfsl|various artists|tone poet|acoustic sounds?|impex|records|sale)\b",
    re.I,
)


def _subtitle(offer: dict, album: str | None) -> str | None:
    """Текст из скобок названия магазина, похожий на часть названия альбома, а не на описание издания:
    «Madame X (Music From The Theater Experience)» → «Music From The Theater Experience»."""
    title = unescape(offer.get("raw_title") or "")
    album_words = set(textmatch.words(album))
    # только скобки после начала названия альбома: «Pink (P!nk) – Funhouse» — это второе имя исполнителя
    start = title.lower().find((album or "").lower()[:20]) if album else -1
    parts = [
        chunk.group(1) for chunk in re.finditer(r"\(([^()]*)\)", title)
        if chunk.start() >= max(start, 0)
        and not _EDITION_NOTE.search(chunk.group(1)) and detect_color(chunk.group(1)) == "black"
        and not detect_qty(chunk.group(1)) and not re.match(r"\s*(with|feat|ft\.|w/|при участии)", chunk.group(1), re.I)
        and len(textmatch.words(chunk.group(1))) >= 2 and not set(textmatch.words(chunk.group(1))) <= album_words
    ]
    return " ".join(parts) or None


def _hints(offer: dict) -> tuple[str | None, str | None]:
    artist = (offer.get("artist_hint") or "").strip() or None
    album = (offer.get("album_hint") or "").strip() or None
    if not album:
        album = re.sub(r"\([^)]*\)|\|.*$", " ", offer.get("raw_title") or "").strip() or None
    return artist, album


def _best(artist: str | None, album: str, results: list[dict], subtitle: str | None = None) -> tuple[dict, bool] | None:
    """Лучший результат поиска Discogs и признак, что в его названии есть подзаголовок из скобок."""
    scored = [
        (textmatch.acceptable(artist, album, r.get("title") or "", subtitle), i, r) for i, r in enumerate(results[:10])
    ]
    scored = [s for s in scored if s[0] > 0]
    if not scored:
        return None
    # при равной оценке — порядок выдачи Discogs (релевантность)
    best = max(scored, key=lambda s: (s[0], -s[1]))[2]
    title = textmatch.split_result_title(best.get("title") or "")[1]
    return best, textmatch.subtitle_coverage(subtitle, title) > 0


def _local_master_by_text(conn, artist: str | None, album: str | None,
                          subtitle: str | None = None) -> tuple[float, int, bool] | None:
    """Альбом уже есть в базе (по названию целиком, без приписок или вместе с подзаголовком из скобок)
    и исполнитель подходит — без запроса к Discogs. (оценка, id, есть ли в названии подзаголовок)."""
    key = title_key(album)
    if len(key) < 2:
        return None
    keys = [key] + ([title_key(f"{album} {subtitle}")] if subtitle else [])
    rows = conn.execute(
        "select id, artist_display, title from master where title_key = any(%s) or core_key = any(%s)", (keys, keys)
    ).fetchall()
    return _best_local(artist, album, rows, subtitle)


def _best_local(artist: str | None, album: str | None, rows,
                subtitle: str | None = None) -> tuple[float, int, bool] | None:
    """Лучший альбом из базы: (оценка, id, есть ли подзаголовок). При равной оценке — настоящий master
    и меньший id (обычно оригинал)."""
    titles = {r["id"]: r["title"] for r in rows}
    scored = [
        (textmatch.acceptable_parts(artist, album, r["artist_display"], r["title"], subtitle), r["id"]) for r in rows
    ]
    best = max((s for s in scored if s[0] > 0), key=lambda s: (s[0], s[1] > 0, -abs(s[1])), default=None)
    return (*best, textmatch.subtitle_coverage(subtitle, titles[best[1]]) > 0) if best else None


def recheck_text(conn, apply: bool = False, samples: int = 60) -> dict:
    """Перепроверяет текстовые сопоставления после изменения правил.

    Если в базе есть альбом, который подходит лучше, позиция переносится на него. Если позиция привязана
    к другому исполнителю с похожим именем («Little Big» → «Little Big Town») или к альбому без подзаголовка
    из скобок («Madame X (Music From The Theater Experience)» → «Madame X»), она снова становится pending
    и найдётся заново при следующем сопоставлении. Без apply только считает и показывает примеры.
    """
    masters = conn.execute("select id, artist_display, title, title_key, core_key from master").fetchall()
    by_key: dict[str, list[dict]] = defaultdict(list)
    for m in masters:
        for key in {m["title_key"], m["core_key"]}:
            if key:
                by_key[key].append(m)
    rows = conn.execute(
        """select o.id, o.artist_hint, o.album_hint, o.raw_title, o.master_id,
                  m.artist_display, m.title, r.title as release_title
           from offer o join master m on m.id = o.master_id left join release r on r.id = o.release_id
           where o.match_status = 'text' and o.in_stock"""
    ).fetchall()
    stats, examples, moves, resets = defaultdict(int), [], [], []
    for row in rows:
        artist, album = _hints(row)
        subtitle = _subtitle(row, album)
        # сопоставляли либо с альбомом в базе, либо с названием издания из поиска Discogs («Kylie* - Disco»)
        found_as = [(row["artist_display"], row["title"])]
        if row["release_title"]:
            found_as.append(textmatch.split_result_title(row["release_title"]))
        current = max(textmatch.acceptable_parts(artist, album, a, t, subtitle) for a, t in found_as)
        has_subtitle = any(textmatch.subtitle_coverage(subtitle, t) > 0 for _, t in found_as)
        keys = [title_key(album)] + ([title_key(f"{album} {subtitle}")] if subtitle else [])
        candidates = list({m["id"]: m for k in keys if len(k) >= 2 for m in by_key.get(k, [])}.values())
        best = _best_local(artist, album, candidates, subtitle)
        if best and best[1] != row["master_id"] and best[0] > current:
            moves.append((best[1], row["id"]))
            stats["moved"] += 1
            target = next(m for m in candidates if m["id"] == best[1])
            change = f"{target['artist_display']} — {target['title']}"
        elif not current and artist and all(textmatch.other_artist(artist, a) for a, _ in found_as):
            resets.append((row["id"],))
            stats["reset"] += 1
            change = "заново искать"
        elif subtitle and not has_subtitle:
            # сопоставлено без учёта подзаголовка (раньше скобки отбрасывались) — ищем ещё раз вместе с ним
            resets.append((row["id"],))
            stats["reset_subtitle"] += 1
            change = f"заново искать с «{subtitle}»"
        else:
            stats["kept"] += 1
            continue
        if len(examples) < samples:
            examples.append(f"{row['raw_title']}: {row['artist_display']} — {row['title']} → {change}")
    if apply:
        with conn.cursor() as cur:
            cur.executemany("update offer set master_id = %s, release_id = null where id = %s", moves)
            cur.executemany(
                "update offer set master_id = null, release_id = null, match_status = 'pending' where id = %s", resets
            )
    log.info("перепроверка текстовых сопоставлений%s: %s", "" if apply else " (без изменений)", dict(stats))
    return {**stats, "applied": apply, "examples": examples}


def _backfill_title_keys(conn) -> None:
    """Заполняет и пересчитывает master.title_key / core_key (например, после изменения правил нормализации)."""
    rows = conn.execute("select id, title, title_key, core_key from master").fetchall()
    stale = [
        (title_key(r["title"]), _core_key(r["title"]), r["id"])
        for r in rows
        if (r["title_key"], r["core_key"]) != (title_key(r["title"]), _core_key(r["title"]))
    ]
    if stale:
        with conn.cursor() as cur:
            cur.executemany("update master set title_key = %s, core_key = %s where id = %s", stale)


def _core_key(title: str | None) -> str:
    return title_key(textmatch.album_core(title or ""))


def _tokens(text: str) -> set[str]:
    return set(textmatch.words(text)) - _STOP_TOKENS


_STOP_TOKENS = {"the", "a", "lp", "vinyl", "and", "of", "black", "gram", "180", "edition", "limited", "coloured", "colored"}


def _album_coverage(offer: dict, release_title: str) -> float:
    """Какая доля слов названия альбома из магазина есть в названии издания Discogs."""
    album = offer.get("album_hint") or re.sub(r"\([^)]*\)", " ", offer.get("raw_title") or "")
    wanted = _tokens(album)
    if not wanted:
        return 1.0
    return len(wanted & _tokens(release_title)) / len(wanted)


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
        "core_key": _core_key(data.get("title")),
    }


def _upsert_master(conn, master_id: int, data: dict) -> None:
    values = master_values(master_id, data)
    values["tracklist"] = Jsonb(values["tracklist"])
    conn.execute(
        """insert into master (id, title, artist_display, year, genres, styles, cover_url, cover_thumb, tracklist,
                               discogs_uri, title_key, core_key)
           values (%(id)s, %(title)s, %(artist_display)s, %(year)s, %(genres)s, %(styles)s,
                   %(cover_url)s, %(cover_thumb)s, %(tracklist)s, %(discogs_uri)s, %(title_key)s, %(core_key)s)
           on conflict (id) do update set
             title = excluded.title, title_key = excluded.title_key, core_key = excluded.core_key,
             artist_display = excluded.artist_display,
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
