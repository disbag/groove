"""Разбор листингов на коротких кусках реальной разметки (по две карточки на магазин)."""

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
