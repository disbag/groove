"""Общие помощники для HTML-адаптеров."""

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

OUT_OF_STOCK = re.compile(r"нет в наличии|под заказ|ожидается|предзаказ|распродан", re.I)


def soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def text(el) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip() if el else ""


def price(value: str | None) -> int | None:
    """«4 100 руб.», «3 990 ₽», «4900» → целое число рублей."""
    if not value:
        return None
    digits = re.sub(r"[^\d]", "", value.split(",")[0])
    return int(digits) if digits else None


def absolute(base: str, url: str | None) -> str | None:
    return urljoin(base, url) if url else None


def image_src(img, base: str) -> str | None:
    if not img:
        return None
    url = img.get("data-src") or img.get("src")
    if not url or url.startswith("data:"):
        return None
    return absolute(base, url)
