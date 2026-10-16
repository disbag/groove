"""Общие помощники для HTML-адаптеров."""

import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

OUT_OF_STOCK = re.compile(r"нет в наличии|под заказ|ожидается|предзаказ|распродан", re.I)


def soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def text(el) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip() if el else ""


_PRICE = re.compile(r"\d{1,3}(?:[ \u00a0\u202f]\d{3})+|\d+")


def price(value: str | None) -> int | None:
    """«4 100 руб.», «3 990 ₽», «4900», «3300.00» → целое число рублей. Берём первое число в строке:
    склеивать все цифры нельзя — «3300.00» стало бы 330000, а «4 990 ₽ 3 990 ₽» — 49903990."""
    match = _PRICE.search(value or "")
    return int(re.sub(r"\D", "", match.group())) if match else None


def absolute(base: str, url: str | None) -> str | None:
    return urljoin(base, url) if url else None


def image_src(img, base: str) -> str | None:
    if not img:
        return None
    url = img.get("data-src") or img.get("src")
    if not url or url.startswith("data:"):
        return None
    return absolute(base, url)


def get_page(http, url: str, params: dict | None = None, first: bool = False) -> str | None:
    """HTML страницы листинга или None, если её нет. Многие магазины за последней страницей отвечают 404 —
    это конец каталога, а не ошибка. На первой странице 404 — ошибка (сменился адрес раздела)."""
    try:
        return http.get(url, params=params).text
    except requests.HTTPError as exc:
        if not first and exc.response is not None and exc.response.status_code == 404:
            return None
        raise
