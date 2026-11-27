"""Dr.Head: HTML-листинг винила с явным статусом наличия."""

import re

from ..http import PoliteSession
from ..models import Offer, Shop
from ..normalize import detect_color, detect_qty, edition_text, split_title, to_price
from . import _html

SHOP = Shop("doctorhead", "Dr.Head", "https://doctorhead.ru", "bitrix_html")
LISTING = f"{SHOP.base_url}/catalog/muzyka/vinilovye-plastinki/"
_EDITION_SUFFIX = re.compile(r"\s+(?:-\s*)?(?:\d{4}\s+-\s+)?(?:(?:colou?red|picture)\s+)?(?:\d+\s*)?LP\s*$", re.I)


def fetch(http: PoliteSession, *, sections: dict | None = None) -> list[Offer]:
    return _html.fetch_numbered_listing(
        http, LISTING, "PAGEN_1", "a.pagination-list__item[href]", parse_listing, sections
    )


def parse_listing(doc) -> list[Offer]:
    offers = []
    for card in doc.select(".catalog-list__item[data-element-id]"):
        link = card.select_one("a.product-descr__link[href]")
        title = _html.text(card.select_one(".product-descr__title"))
        if not link or not title:
            raise ValueError("В карточке Dr.Head отсутствует название или ссылка")
        price = card.select_one(".product-price[data-price]")
        stock = _html.text(card.select_one(".product-status")).casefold()
        artist, album = split_title(_EDITION_SUFFIX.sub("", title))
        if not artist:
            for field in card.select(".product-text p"):
                label, _, value = _html.text(field).partition(":")
                if label.casefold() == "исполнитель":
                    artist = value.strip() or None
                    break
        suffix = _EDITION_SUFFIX.search(title)
        edition = edition_text(title) or (suffix.group().strip() if suffix else None)
        offers.append(Offer(
            external_id=card["data-element-id"],
            url=_html.absolute(SHOP.base_url, link["href"]),
            raw_title=title,
            price=to_price(price["data-price"]) if price else None,
            in_stock=stock == "в наличии",
            stock_unknown=not stock,
            artist_hint=artist,
            album_hint=album,
            color=detect_color(edition),
            color_raw=edition,
            format_qty=detect_qty(edition) or detect_qty(suffix.group() if suffix else None),
            image_url=_html.image_src(card.select_one(".product-image img"), SHOP.base_url),
        ))
    return offers
