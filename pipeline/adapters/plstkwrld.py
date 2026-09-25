"""PLSTK WRLD (plstkwrld.com, бывший plstkwrld.ru) — Мегагрупп. Каталог разбит на папки-жанры;
список папок берём с /magazin, одинаковые позиции из разных папок склеиваются по product_id.
Штрихкод («Баркод») есть прямо в листинге.
"""

import re

from ..http import PoliteSession
from ..models import Offer, Shop
from . import _html, _megagroup

SHOP = Shop(code="plstkwrld", name="PLSTK WRLD", base_url="https://plstkwrld.com", adapter="megagroup_html")
SKIP_FOLDERS = re.compile(r"accessor|book|hifi|merch|gift|sertif|certificate|cassette|kasset|\bcd\b|poster", re.I)


def fetch(http: PoliteSession) -> list[Offer]:
    doc = _html.soup(http.get(f"{SHOP.base_url}/magazin").text)
    folders = sorted({
        a["href"].split("?")[0].rstrip("/")
        for a in doc.select('a[href^="/magazin/folder/"]')
        if not SKIP_FOLDERS.search(a["href"])
    })
    offers: dict[str, Offer] = {}
    for folder in folders:
        _megagroup.fetch_folder(http, SHOP.base_url, folder, offers)
    return list(offers.values())
