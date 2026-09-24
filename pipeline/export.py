"""Выгрузка статических JSON для сайта: каталог постранично, карточки, поиск, метаданные."""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

PAGE_SIZE = 48
SORTS = {
    "new": lambda c: (-c["first_seen_at"].timestamp(), c["id"]),
    "price": lambda c: (c["min_price"], c["artist_display"].lower()),
    "az": lambda c: (c["artist_display"].lower(), c["title"].lower()),
}
# Жанры Discogs → адрес страницы и русское название (порядок = порядок на сайте)
GENRES = [
    ("rock", "Rock", "Рок"),
    ("electronic", "Electronic", "Электроника"),
    ("pop", "Pop", "Поп"),
    ("hip-hop", "Hip Hop", "Хип-хоп"),
    ("jazz", "Jazz", "Джаз"),
    ("funk-soul", "Funk / Soul", "Фанк и соул"),
    ("stage-screen", "Stage & Screen", "Саундтреки"),
    ("classical", "Classical", "Классика"),
    ("folk-world-country", "Folk, World, & Country", "Фолк и кантри"),
    ("reggae", "Reggae", "Регги"),
    ("blues", "Blues", "Блюз"),
    ("latin", "Latin", "Латино"),
    ("childrens", "Children's", "Детская"),
    ("non-music", "Non-Music", "Не музыка"),
    ("brass-military", "Brass & Military", "Духовая и военная"),
]
GENRE_SLUG = {name: slug for slug, name, _ in GENRES}


def run(conn, out_dir: Path) -> dict:
    cards = conn.execute("select * from catalog_card").fetchall()
    offers = conn.execute(
        """select o.master_id, o.price, o.url, o.color, o.color_raw, o.format_qty, o.image_url,
                  s.code as shop, s.name as shop_name,
                  r.year as r_year, r.country, r.label, r.catno, r.format_desc
           from offer o
           join shop s on s.id = o.shop_id
           left join release r on r.id = o.release_id
           where o.in_stock and o.price is not null and o.master_id is not null
           order by o.price"""
    ).fetchall()
    masters = {
        row["id"]: row
        for row in conn.execute(
            "select id, tracklist from master where id = any(%s)", ([c["id"] for c in cards],)
        )
    }
    shops = conn.execute(
        """select s.code, s.name, s.base_url, count(o.id) filter (where o.in_stock and o.master_id is not null) as offers
           from shop s left join offer o on o.shop_id = s.id
           where s.is_active group by s.id order by s.name"""
    ).fetchall()

    by_master: dict[int, list[dict]] = {}
    for offer in offers:
        by_master.setdefault(offer["master_id"], []).append(offer)

    if out_dir.exists():
        shutil.rmtree(out_dir)
    (out_dir / "card").mkdir(parents=True)

    # Обложка: Discogs, а если её нет — фото из самого дешёвого предложения магазина
    for card in cards:
        fallback = next((o["image_url"] for o in by_master.get(card["id"], []) if o["image_url"]), None)
        card["thumb"] = card["cover_thumb"] or fallback
        card["cover"] = card["cover_url"] or fallback

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for card in cards:
        _write(out_dir / "card" / f"{card['id']}.json", _card_json(card, by_master.get(card["id"], []),
                                                                  masters.get(card["id"]), now))

    groups = {"all": cards}
    for card in cards:
        for genre in card["genres"] or []:
            if genre in GENRE_SLUG:
                groups.setdefault(GENRE_SLUG[genre], []).append(card)
    pages = 0
    for slug, items in groups.items():
        for sort, key in SORTS.items():
            ordered = sorted(items, key=key)
            total_pages = max(1, -(-len(ordered) // PAGE_SIZE))
            for page in range(total_pages):
                chunk = ordered[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]
                _write(out_dir / "catalog" / slug / sort / f"{page + 1}.json", {
                    "page": page + 1, "pages": total_pages, "total": len(ordered),
                    "items": [_list_item(c) for c in chunk],
                })
                pages += 1

    _write(out_dir / "search.json", [
        [c["id"], f"{c['artist_display']} — {c['title']}", c["year"], c["min_price"]]
        for c in sorted(cards, key=SORTS["az"])
    ])
    meta = {
        "generated_at": now,
        "albums": len(cards),
        "offers": len(offers),
        "shops": [{"code": s["code"], "name": s["name"], "url": s["base_url"], "offers": s["offers"]} for s in shops],
        "genres": [
            {"slug": slug, "name": name, "ru": ru, "count": len(groups.get(slug, []))}
            for slug, name, ru in GENRES if groups.get(slug)
        ],
        "page_size": PAGE_SIZE,
    }
    _write(out_dir / "meta.json", meta)
    return {"albums": len(cards), "offers": len(offers), "catalog_pages": pages}


def _list_item(card: dict) -> dict:
    return {
        "id": card["id"], "a": card["artist_display"], "t": card["title"], "y": card["year"],
        "c": card["thumb"], "cv": card["cover"], "p": card["min_price"], "n": card["shops_in_stock"],
        "col": card["has_coloured"],
    }


def _card_json(card: dict, offers: list[dict], master: dict | None, now: str) -> dict:
    return {
        "id": card["id"],
        "artist": card["artist_display"],
        "title": card["title"],
        "year": card["year"],
        "genres": card["genres"],
        "styles": card["styles"],
        "cover": card["cover"],
        "discogs": card["discogs_uri"],
        "min_price": card["min_price"],
        "tracklist": (master or {}).get("tracklist") or [],
        "offers": [
            {
                "shop": o["shop"], "shop_name": o["shop_name"], "price": o["price"], "url": o["url"],
                "color": o["color"], "color_raw": o["color_raw"], "lp": o["format_qty"],
                "year": o["r_year"], "country": o["country"], "label": o["label"], "catno": o["catno"],
            }
            for o in offers
        ],
        "updated": now,
    }


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
