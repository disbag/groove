"""Общий разбор листингов платформы Мегагрупп (shop2): sferazvyka.ru, plstkwrld.com.

Карточка — <form class="shop2-product-item"> со скрытым product_id; параметры («Формат: …», «Баркод: …»)
идут парами «ключ: значение». Пагинация: папка, затем /p/1, /p/2, …
"""

import re

from ..http import PoliteSession
from ..models import Offer
from ..normalize import (
    clean_barcode, detect_color, detect_qty, edition_text, split_title,
)
from . import _html

TITLE_PREFIX = re.compile(r"^виниловая пластинка\s+", re.I)
NON_VINYL_FORMAT = re.compile(r"\b(CD|Cassette|Кассета|DVD|Blu-?ray)\b", re.I)


def fetch_folder(http: PoliteSession, base_url: str, folder: str, into: dict[str, Offer]) -> None:
    """Обходит страницы папки и добавляет новые позиции в into (по product_id)."""
    for page in range(0, 500):
        url = f"{base_url}{folder}" + (f"/p/{page}" if page else "")
        html = _html.get_page(http, url, first=page == 0)
        if html is None:
            break  # у папки меньше страниц: /p/N отвечает 404
        batch = parse_listing(html, base_url)
        fresh = [o for o in batch if o.external_id not in into]
        if not batch or (page and not fresh and all(o.external_id in into for o in batch)):
            break
        into.update((o.external_id, o) for o in fresh)


def parse_listing(html: str, base_url: str) -> list[Offer]:
    doc = _html.soup(html)
    offers: dict[str, Offer] = {}
    for card in doc.select("form.shop2-product-item"):
        pid = card.select_one("input[name=product_id]")
        link = card.select_one(".product-item__name a[href], .product-name a[href]")
        if not pid or not link or pid["value"] in offers:
            continue
        params = _params(card)
        fmt = params.get("Формат") or ""
        if fmt and NON_VINYL_FORMAT.search(fmt) and not re.search(r"LP|Vinyl|винил", fmt, re.I):
            continue
        title = TITLE_PREFIX.sub("", _html.text(link))
        artist, album = split_title(title)
        edition = " ".join(x for x in (edition_text(title), fmt) if x) or None
        offers[pid["value"]] = Offer(
            external_id=pid["value"],
            url=_html.absolute(base_url, link["href"]),
            raw_title=title,
            price=_price(card),
            in_stock=not _html.OUT_OF_STOCK.search(_html.text(card)),
            barcode=clean_barcode(params.get("Баркод") or params.get("Штрихкод")),
            artist_hint=params.get("Исполнитель") or artist,
            album_hint=album,
            color=detect_color(edition),
            color_raw=edition,
            format_qty=detect_qty(fmt) or detect_qty(edition),
            image_url=_html.image_src(card.select_one("img"), base_url),
        )
    return list(offers.values())


def _params(card) -> dict[str, str]:
    """«Формат: LP, Album» или «Артикул:» + «нет» отдельной строкой → словарь."""
    params, pending = {}, None
    for part in card.stripped_strings:
        if pending:
            params.setdefault(pending, part)
            pending = None
            continue
        if ":" in part:
            key, value = part.split(":", 1)
            key, value = key.strip(), value.strip()
            if value:
                params.setdefault(key, value)
            elif key:
                pending = key
    return params


def _price(card) -> int | None:
    el = card.select_one(".price-current")
    if el:
        return _html.price(_html.text(el))
    match = re.search(r"(\d[\d\s]*)\s*(?:руб|р\.|₽)", _html.text(card))
    return _html.price(match.group(1)) if match else None
