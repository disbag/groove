"""Стереозона (stereozona.ru) — 1С-Битрикс. Раздел пластинок, 24 позиции на странице.

В карточке: исполнитель, альбом, цена. Штрихкод и цвет — на странице товара, поэтому сопоставляем по названию,
а цвет берём из названия, если он там указан.
"""

from ..http import PoliteSession
from ..models import Offer, Shop
from ..normalize import album_before_parentheses, detect_color, detect_qty, edition_text
from . import _html

SHOP = Shop(code="stereozona", name="Стереозона", base_url="https://stereozona.ru", adapter="bitrix_html")
LISTING = f"{SHOP.base_url}/catalog/plastinki/"


def fetch(http: PoliteSession) -> list[Offer]:
    offers: dict[str, Offer] = {}
    for page in range(1, 500):
        html = _html.get_page(http, LISTING, {"PAGEN_1": page}, first=page == 1)
        if html is None:
            break
        batch = parse_listing(html)
        fresh = [o for o in batch if o.external_id not in offers]
        if not fresh:
            break
        offers.update((o.external_id, o) for o in fresh)
    return list(offers.values())


def parse_listing(html: str) -> list[Offer]:
    doc = _html.soup(html)
    offers = []
    for card in doc.select("div.product-item[data-product-item]"):
        link = card.select_one("a.product-item__link[href]")
        album = _html.text(card.select_one(".product-item__title"))
        if not link or not album:
            continue
        artist = _html.text(card.select_one(".product-item__sub-title")) or None
        card_text = _html.text(card)
        edition = edition_text(album)
        offers.append(Offer(
            external_id=card["data-product-id"],
            url=_html.absolute(SHOP.base_url, link["href"]),
            raw_title=f"{artist} – {album}" if artist else album,
            price=_html.price(_html.text(card.select_one(".product-item__price"))),
            in_stock=not _html.OUT_OF_STOCK.search(card_text),
            artist_hint=artist,
            album_hint=album_before_parentheses(album),
            color=detect_color(edition),
            color_raw=edition,
            format_qty=detect_qty(edition),
            image_url=_html.image_src(card.select_one("img.product-item__image"), SHOP.base_url),
        ))
    return offers

