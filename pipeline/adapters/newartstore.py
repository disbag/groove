"""«Новое искусство» (newartstore.ru) — 1С-Битрикс. Раздел «Новый винил», 48 позиций на странице.

В карточке: альбом, исполнитель (в скобках, заглавными), формат («LP, Coloured»), цена. Всё в каталоге — в наличии,
кнопка покупки несёт avail="1". Штрихкод только на странице товара — сопоставляем по названию.
"""

import re

from ..http import PoliteSession
from ..models import Offer, Shop
from ..normalize import detect_color, detect_qty
from . import _html

SHOP = Shop(code="newartstore", name="Новое искусство", base_url="https://newartstore.ru", adapter="bitrix_html")
LISTING = f"{SHOP.base_url}/catalog/vinilovye_plastinki/"


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
    for card in doc.select("div.product[id^=bx_]"):
        name = card.select_one(".name a[href]")
        if not name:
            continue
        album = _html.text(name)
        artist = _html.text(card.select_one(".author")).strip("() ") or None
        # формат — «голый» текст между исполнителем и ценой
        fmt = " ".join(
            s.strip() for s in card.find_all(string=True, recursive=False) if s.strip()
        ) or None
        buy = card.select_one(".buy a[avail]")
        offers.append(Offer(
            external_id=card["id"].rsplit("_", 1)[-1],
            url=_html.absolute(SHOP.base_url, name["href"]),
            raw_title=f"{artist} – {album}" + (f" ({fmt})" if fmt else "") if artist else album,
            price=_html.price(_html.text(card.select_one(".price"))),
            in_stock=bool(buy) and buy.get("avail") == "1",
            artist_hint=artist,
            album_hint=re.sub(r"\s*\([^)]*\)\s*$", "", album) or album,
            color=detect_color(fmt),
            color_raw=fmt,
            format_qty=detect_qty(fmt),
            image_url=_html.image_src(card.select_one(".thumb img"), SHOP.base_url),
        ))
    return offers
