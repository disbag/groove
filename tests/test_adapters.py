"""Разбор листингов на коротких кусках реальной разметки (по две карточки на магазин)."""

import re
from pathlib import Path

from pipeline.adapters import _megagroup, newartstore, stereozona, vidika, vinylis

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> str:
    return (FIXTURES / f"{name}.html").read_text(encoding="utf-8")


def test_vinylis():
    offers = vinylis.parse_listing(load("vinylis"))
    assert [o.external_id for o in offers] == ["57997", "81908"]
    first, second = offers
    assert (first.artist_hint, first.album_hint, first.price) == ("КИНО", "Звезда По Имени Солнце", 3300)
    assert first.in_stock and first.color == "black" and first.format_qty == 1
    assert second.color == "coloured"
    assert first.url.startswith("https://vinyl-is.ru/catalog/vinilovye_plastinki/")


def test_newartstore():
    first = newartstore.parse_listing(load("newart"))[0]
    assert (first.external_id, first.artist_hint, first.album_hint) == ("656814", "CROSSES", "Permanent.Radiant")
    assert first.price == 4100 and first.in_stock and first.color == "coloured"


def test_vidika():
    first = vidika.parse_listing(load("vidika"))[0]
    assert (first.artist_hint, first.album_hint) == ("2Pac", "Part 2: Life")
    assert first.price == 4770  # текущая цена, не старая и не артикул
    assert first.color == "coloured" and first.format_qty == 2 and first.in_stock


def test_stereozona():
    first = stereozona.parse_listing(load("stereo"))[0]
    assert (first.external_id, first.artist_hint, first.album_hint, first.price) == ("39927", "ABBA", "Gold: Greatest Hits", 3990)


def test_megagroup_sferazvyka():
    first = _megagroup.parse_listing(load("sfera"), "https://sferazvyka.ru")[0]
    assert (first.artist_hint, first.album_hint, first.price) == ("2 Unlimited", "No Limits!", 4200)
    assert first.format_qty == 2 and first.in_stock


def test_megagroup_plstkwrld_barcode():
    first = _megagroup.parse_listing(load("plstk"), "https://plstkwrld.com")[0]
    assert first.barcode == "199350824630"
    assert first.album_hint == "Thy Kingdom Come" and first.color == "clear" and first.price == 4900


class FakeHttp:
    """Отдаёт одну и ту же страницу на любой номер — как Битрикс за последней страницей."""

    def __init__(self, html: str):
        self.html, self.calls = html, 0

    def throttle(self, url, seconds):
        pass

    def get(self, url, params=None):
        self.calls += 1
        return type("Response", (), {"text": self.html})()


def test_pagination_stops_on_repeated_page():
    http = FakeHttp(load("vinylis"))
    offers = vinylis.fetch(http)
    assert len(offers) == 2 and http.calls == 2


class NotFoundAfterFirst(FakeHttp):
    """Первая страница есть, дальше 404 — как у vinyl-is, plstkwrld и sferazvyka."""

    def get(self, url, params=None):
        import requests

        self.calls += 1
        if self.calls > 1:
            response = requests.Response()
            response.status_code = 404
            raise requests.HTTPError("404", response=response)
        return type("Response", (), {"text": self.html})()


def test_pagination_stops_on_404():
    http = NotFoundAfterFirst(load("vinylis"))
    assert len(vinylis.fetch(http)) == 2
    offers = {}
    _megagroup.fetch_folder(NotFoundAfterFirst(load("plstk")), "https://plstkwrld.com", "/magazin/folder/x", offers)
    assert len(offers) == 2


def test_first_page_404_is_an_error():
    import pytest
    import requests

    class AlwaysNotFound(NotFoundAfterFirst):
        def get(self, url, params=None):
            self.calls = 1
            return super().get(url, params)

    with pytest.raises(requests.HTTPError):
        vinylis.fetch(AlwaysNotFound(""))


def test_megagroup_folder_overlapping_other_folder():
    """Страница папки, целиком уже встреченная в другой папке, — не конец папки (жанры plstkwrld пересекаются)."""
    page = load("plstk")
    ids = re.findall(r'name="product_id" type="hidden" value="(\d+)"', page)
    assert len(ids) == 2
    first, last = page, page
    for pid in ids:
        first = first.replace(f'value="{pid}"', f'value="8{pid}"')
        last = last.replace(f'value="{pid}"', f'value="9{pid}"')
    pages = {"/rock": page, "/pop": first, "/pop/p/1": page, "/pop/p/2": last}

    class Folders(FakeHttp):
        def get(self, url, params=None):
            path = url.removeprefix("https://plstkwrld.com")
            if path not in pages:
                _not_found()
            return type("Response", (), {"text": pages[path]})()

    offers = {}
    http = Folders("")
    _megagroup.fetch_folder(http, "https://plstkwrld.com", "/rock", offers)
    _megagroup.fetch_folder(http, "https://plstkwrld.com", "/pop", offers)
    # вторая страница /pop целиком из /rock, но на третьей — снова новые позиции
    assert len(offers) == 6


def _not_found():
    import requests

    response = requests.Response()
    response.status_code = 404
    raise requests.HTTPError("404", response=response)
