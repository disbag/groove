"""Пульт (pult.ru) — список товаров лежит JSON-массивом `catalogListParams.products` прямо в HTML листинга.

Листинг отсортирован так, что товары в наличии идут первыми; после двух страниц подряд
без единой позиции в наличии обход останавливается.
"""

import json
import re

from ..http import PoliteSession
from ..models import Offer, Shop
from ..normalize import clean_barcode, color_part_of_title, detect_color, detect_qty, strip_parentheses, to_price, unescape

SHOP = Shop(code="pult", name="Пульт", base_url="https://www.pult.ru", adapter="pult_embedded_json")
LISTING = f"{SHOP.base_url}/product/vinilovye-plastinki-new/"
TITLE_PREFIX = re.compile(r"^виниловая пластинка\s+", re.I)


def fetch(http: PoliteSession) -> list[Offer]:
    offers: list[Offer] = []
    seen_ids: set[str] = set()
    empty_pages = 0
    for page in range(1, 1000):
        products = extract_products(http.get(LISTING, params={"PAGEN_1": page}).text)
        fresh = [p for p in products if str(p.get("id")) not in seen_ids]
        if not fresh:
            break  # вышли за последнюю страницу: Битрикс отдаёт её повторно
        in_stock = 0
        for product in fresh:
            seen_ids.add(str(product.get("id")))
            offer = _parse(product)
            if offer.in_stock:
                in_stock += 1
                offers.append(offer)
        empty_pages = 0 if in_stock else empty_pages + 1
        if empty_pages >= 2:
            break
    return offers


def extract_products(page_html: str) -> list[dict]:
    start = page_html.find("products: [")
    if start < 0:
        return []
    start = page_html.index("[", start)
    depth, in_string, escaped = 0, False, False
    for pos in range(start, len(page_html)):
        char = page_html[pos]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return json.loads(page_html[start:pos + 1])
    return []


def _parse(product: dict) -> Offer:
    params = {p.get("label"): unescape(str(p.get("value"))) for p in product.get("params") or []}
    title = unescape(product.get("name"))
    clean_title = TITLE_PREFIX.sub("", title)
    artist = params.get("Исполнители")
    album = None
    if artist and clean_title.lower().startswith(artist.lower()):
        album = strip_parentheses(clean_title[len(artist):].lstrip(" -–—"))
    color_raw = color_part_of_title(title)
    qty = params.get("Количество пластинок")
    image = product.get("image")
    return Offer(
        external_id=str(product.get("id")),
        url=SHOP.base_url + product.get("link", ""),
        raw_title=clean_title,
        price=to_price((product.get("price") or {}).get("current")),
        in_stock=bool(product.get("available")),
        barcode=clean_barcode(product.get("barcode") or params.get("Barcode")),
        artist_hint=artist,
        album_hint=album or None,
        color=detect_color(color_raw),
        color_raw=color_raw,
        format_qty=int(qty) if qty and qty.isdigit() else detect_qty(color_raw),
        image_url=(SHOP.base_url + image) if image and image.startswith("/") else image,
    )
