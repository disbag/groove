"""«Сфера звука» (sferazvyka.ru) — Мегагрупп. Только папка «Новый винил»; винтаж и уценка лежат в других папках."""

from ..http import PoliteSession
from ..models import Offer, Shop
from . import _megagroup

SHOP = Shop(code="sferazvyka", name="Сфера звука", base_url="https://sferazvyka.ru", adapter="megagroup_html")
FOLDER = "/shop/folder/novye"


def fetch(http: PoliteSession) -> list[Offer]:
    offers: dict[str, Offer] = {}
    _megagroup.fetch_folder(http, SHOP.base_url, FOLDER, offers)
    return list(offers.values())
