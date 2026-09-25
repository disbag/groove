"""Видика (vidika.su) — Webasyst Shop-Script. Берём только категории с пластинками в наличии.

Большая часть каталога (~60 тыс.) — «под заказ» со сроком 2–3 месяца, её не показываем.
В карточке: «Виниловая пластинка Артист - Альбом (2LP) Grey», исполнитель, «В наличии», цена и старая цена.
"""

import re

from ..http import PoliteSession
from ..models import Offer, Shop
from ..normalize import detect_color, detect_qty, edition_text, split_title
from . import _html

SHOP = Shop(code="vidika", name="Видика", base_url="https://vidika.su", adapter="webasyst_html")
CATEGORIES = ["/category/zarubezhnyy-vinil/", "/category/russkiy-vinil/"]
TITLE_PREFIX = re.compile(r"^виниловая пластинка\s+", re.I)


def fetch(http: PoliteSession) -> list[Offer]:
    offers: dict[str, Offer] = {}
    for category in CATEGORIES:
        seen_in_category: set[str] = set()
        for page in range(1, 500):
            batch = parse_listing(http.get(SHOP.base_url + category, params={"page": page}).text)
            fresh = [o for o in batch if o.external_id not in seen_in_category]
            if not fresh:
                break
            seen_in_category.update(o.external_id for o in fresh)
            offers.update((o.external_id, o) for o in fresh)
    return list(offers.values())


def parse_listing(html: str) -> list[Offer]:
    doc = _html.soup(html)
    offers = []
    for card in doc.select("div.products__item"):
        link = card.select_one("a[href]")
        pid = card.select_one("[data-product-id]")
        img = card.select_one("img[alt]")
        if not link or not pid or not img:
            continue
        title = TITLE_PREFIX.sub("", img["alt"]).strip()
        card_text = _html.text(card)
        match = re.search(r"Исполнитель:\s*(.+?)\s+(?:В наличии|Под заказ|Нет в наличии|Предзаказ|Артикул)", card_text)
        artist_hint = match.group(1).strip() if match else None
        artist, album = split_title(title)
        edition = edition_text(title)
        offers.append(Offer(
            external_id=pid["data-product-id"],
            url=_html.absolute(SHOP.base_url, link["href"]),
            raw_title=title,
            price=_html.price(_html.text(card.select_one(".products__pr-price-new .price, .products__pr-price .price"))),
            in_stock="В наличии" in card_text and not re.search(r"Под заказ|Нет в наличии|Предзаказ", card_text),
            artist_hint=artist_hint or artist,
            album_hint=album,
            color=detect_color(edition),
            color_raw=edition,
            format_qty=detect_qty(edition),
            image_url=_html.image_src(img, SHOP.base_url),
        ))
    return offers
