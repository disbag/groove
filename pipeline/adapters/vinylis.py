"""vinyl-is.ru — 1С-Битрикс (шаблон Aspro). Данные карточки лежат в data-атрибутах кнопки «В корзину».

Штрихкод есть только на странице товара, поэтому обходим только листинг и сопоставляем по названию.
robots.txt просит Crawl-delay: 2.
"""

from ..http import PoliteSession
from ..models import Offer, Shop
from ..normalize import (
    detect_color, detect_qty, edition_text, split_title,
)
from . import _html

SHOP = Shop(code="vinylis", name="Vinyl-is", base_url="https://vinyl-is.ru", adapter="bitrix_aspro_html")
LISTING = f"{SHOP.base_url}/catalog/vinilovye_plastinki/"
CRAWL_DELAY = 2.0


def fetch(http: PoliteSession) -> list[Offer]:
    http.throttle(LISTING, CRAWL_DELAY)
    offers: dict[str, Offer] = {}
    for page in range(1, 1000):
        batch = parse_listing(http.get(LISTING, params={"PAGEN_1": page}).text)
        fresh = [o for o in batch if o.external_id not in offers]
        if not fresh:
            break  # за последней страницей Битрикс отдаёт её же
        offers.update((o.external_id, o) for o in fresh)
    return list(offers.values())


def parse_listing(html: str) -> list[Offer]:
    doc = _html.soup(html)
    offers = []
    for info in doc.select("div.item_info.main_item_wrapper"):
        button = info.select_one("[data-id][data-name][data-price]")
        link = info.select_one(".item-title a[href]")
        if not button or not link:
            continue
        title = button["data-name"]
        stock = _html.text(info.select_one(".item-stock .value"))
        card = info.parent
        artist, album = split_title(title)
        edition = edition_text(title)
        offers.append(Offer(
            external_id=button["data-id"],
            url=_html.absolute(SHOP.base_url, link["href"]),
            raw_title=title,
            price=_html.price(button.get("data-price")),
            in_stock=not _html.OUT_OF_STOCK.search(stock),
            artist_hint=artist,
            album_hint=album,
            color=detect_color(edition),
            color_raw=edition,
            format_qty=detect_qty(button.get("data-variant")) or detect_qty(edition),
            image_url=_html.image_src(card.select_one("img[data-src], img[src]") if card else None, SHOP.base_url),
        ))
    return offers
