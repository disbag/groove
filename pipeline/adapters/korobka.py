"""«Коробка винила» (korobkavinyla.ru) — Tilda Store API.

Фильтры те же, что использует сам сайт: раздел «Винил» и «только в наличии».
Без фильтров API отдаёт не больше 12 срезов по 500 товаров и потом начинает отдавать срезы по кругу,
поэтому пройденные срезы запоминаем.
"""

import re

from ..http import PoliteSession
from ..models import Offer, Shop
from ..normalize import (
    clean_barcode, color_part_of_title, detect_color, detect_qty, split_artist_album, to_price, unescape,
)

SHOP = Shop(code="korobka", name="Коробка винила", base_url="https://korobkavinyla.ru", adapter="tilda_api")
API = "https://store.tildaapi.com/api/getproductslist/"
STOREPART_UID = "974505268935"
REC_ID = "771567999"
USED_PARTS = {"Used", "VINTAGE", "Редкий Винтаж"}


def fetch(http: PoliteSession) -> list[Offer]:
    params = {
        "storepartuid": STOREPART_UID,
        "recid": REC_ID,
        "getparts": "true",
        "getoptions": "false",
        "size": "500",
        "filters[storepartuid][0]": "Винил",
        "filters[quantity]": "y",
        "sort[created]": "desc",
    }
    headers = {"Referer": f"{SHOP.base_url}/catalog"}
    used_part_ids: set[str] = set()
    offers: list[Offer] = []
    slice_no, seen = 1, set()
    while slice_no and slice_no not in seen:
        seen.add(slice_no)
        data = http.get(API, params={**params, "slice": str(slice_no)}, headers=headers).json()
        for part in data.get("parts") or []:
            if part.get("title") in USED_PARTS:
                used_part_ids.add(str(part.get("uid")))
        for product in data.get("products") or []:
            offer = _parse(product, used_part_ids)
            if offer:
                offers.append(offer)
        slice_no = data.get("nextslice")
    return offers


def _field(descr: str, *names: str) -> str | None:
    for name in names:
        match = re.search(rf"{name}\s*:\s*([^\n]+)", descr, re.I)
        if match:
            return match.group(1).strip()
    return None


def _parse(product: dict, used_part_ids: set[str]) -> Offer | None:
    parts = set(re.findall(r"\d+", product.get("partuids") or ""))
    if parts & used_part_ids:
        return None
    editions = product.get("editions") or [{}]
    quantity = max(float(e.get("quantity") or 0) for e in editions)
    title = unescape(product.get("title"))
    descr = unescape(re.sub(r"<br\s*/?>", "\n", product.get("descr") or "", flags=re.I))
    fmt = _field(descr, "Format", "Формат") or ""
    color_raw = color_part_of_title(title) or fmt or None
    artist, album = split_artist_album(title)
    gallery = product.get("gallery")
    image = editions[0].get("img")
    if not image and isinstance(gallery, str):
        match = re.search(r'"img"\s*:\s*"([^"]+)"', gallery)
        image = match.group(1) if match else None
    return Offer(
        external_id=str(product.get("uid")),
        url=product.get("url") or f"{SHOP.base_url}/catalog",
        raw_title=title,
        price=to_price(product.get("price") or editions[0].get("price")),
        in_stock=quantity > 0,
        barcode=clean_barcode(product.get("sku") or editions[0].get("sku")),
        artist_hint=artist,
        album_hint=album,
        color=detect_color(color_raw),
        color_raw=color_raw,
        format_qty=detect_qty(fmt) or detect_qty(title),
        image_url=image,
    )
