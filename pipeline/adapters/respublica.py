"""Республика: HTML-листинг пластинок с ценой и наличием в разметке schema.org."""

import re

from ..http import PoliteSession
from ..models import Offer, Shop
from ..normalize import clean_barcode, detect_color, detect_qty, edition_text, split_title, to_price
from . import _html

SHOP = Shop("respublica", "Республика", "https://www.respublica.ru", "schema_org_html")
LISTING = f"{SHOP.base_url}/muzyka-na-vinile"
_LP_SUFFIX = re.compile(r"\s+(?:\d+\s*)?LP\s*$", re.I)


def fetch(http: PoliteSession, *, sections: dict | None = None) -> list[Offer]:
    return _html.fetch_numbered_listing(
        http, LISTING, "page", "a.pages-item-link[href]", parse_listing, sections
    )


def parse_listing(doc) -> list[Offer]:
    offers = []
    for card in doc.select('main [itemtype$="/Product"]'):
        link = card.select_one('h3 a[href^="/muzyka-na-vinile/vinilovye-plastinki/"]')
        if not link:
            continue
        title = _html.text(link)
        sku = _meta(card, "sku")
        if not title or not sku:
            raise ValueError("В карточке Республики отсутствует название или SKU")
        stock = (_meta(card, "availability") or "").rsplit("/", 1)[-1]
        artist, album = split_title(_LP_SUFFIX.sub("", title))
        edition = edition_text(title)
        suffix = _LP_SUFFIX.search(title)
        offers.append(Offer(
            external_id=sku,
            url=_html.absolute(SHOP.base_url, link["href"]),
            raw_title=title,
            price=to_price(_meta(card, "price")),
            in_stock=stock == "InStock",
            stock_unknown=not stock,
            barcode=clean_barcode(_meta(card, "gtin13") or _meta(card, "gtin12") or _meta(card, "gtin")),
            artist_hint=artist,
            album_hint=album,
            color=detect_color(edition),
            color_raw=edition,
            format_qty=detect_qty(suffix.group() if suffix else edition),
            image_url=_html.image_src(card.select_one("a.images img"), SHOP.base_url),
        ))
    return offers


def _meta(card, field: str) -> str | None:
    element = card.select_one(f'[itemprop="{field}"][content]')
    return element["content"] if element else None
