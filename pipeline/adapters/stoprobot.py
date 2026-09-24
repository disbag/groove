"""Stoprobot (stoprobot.ru) — InSales. Публичный JSON коллекции: только позиции в наличии, 100 на страницу."""

import re

from ..http import PoliteSession
from ..models import Offer, Shop
from ..normalize import clean_barcode, color_part_of_title, detect_color, detect_qty, to_price, unescape

SHOP = Shop(code="stoprobot", name="Stoprobot", base_url="https://stoprobot.ru", adapter="insales_json")
COLLECTION = "vinilovye-plastinki"


def fetch(http: PoliteSession) -> list[Offer]:
    offers: list[Offer] = []
    for page in range(1, 500):
        data = http.get(f"{SHOP.base_url}/collection/{COLLECTION}.json", params={"page": page}).json()
        products = data.get("products") or []
        if not products:
            break
        for product in products:
            offer = _parse(product)
            if offer:
                offers.append(offer)
    return offers


def _parse(product: dict) -> Offer | None:
    titles = {prop["id"]: prop["title"] for prop in product.get("properties", [])}
    chars = {titles.get(c.get("property_id")): unescape(c.get("title")) for c in product.get("characteristics", [])}

    if (chars.get("Состояние") or "New").strip().lower() != "new":
        return None  # в MVP только новый винил
    fmt = chars.get("Формат") or ""
    if fmt and not re.search(r"lp|винил|vinyl|\d+\"|box", fmt, re.I):
        return None  # CD, кассеты, аксессуары

    variant = (product.get("variants") or [{}])[0]
    title = unescape(product.get("title"))
    if re.search(r"\|\s*used\b", title, re.I):
        return None  # б/у, у которых забыли поменять «Состояние»
    color_raw = chars.get("Цвет") or color_part_of_title(title)
    image = product.get("first_image") or ((product.get("images") or [None])[0]) or {}
    return Offer(
        external_id=str(product["id"]),
        url=SHOP.base_url + product["url"],
        raw_title=title,
        price=to_price(variant.get("price") or product.get("price_min")),
        in_stock=bool(product.get("available")) and bool(variant.get("available", True)),
        barcode=clean_barcode(variant.get("barcode")),
        artist_hint=chars.get("Исполнитель"),
        album_hint=chars.get("Альбом"),
        color=detect_color(color_raw),
        color_raw=color_raw,
        format_qty=detect_qty(fmt) or detect_qty(title),
        image_url=_image_url(image),
    )


def _image_url(image: dict) -> str | None:
    url = image.get("large_url") or image.get("original_url") or image.get("url")
    if not url or "no_image" in url:
        return None
    return url
