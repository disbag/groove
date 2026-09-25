from pipeline.adapters.pult import extract_products
from pipeline.match import _album_coverage, _text_query, master_values
from pipeline.normalize import (
    barcode_key, clean_barcode, clean_discogs_name, color_part_of_title, detect_color, detect_qty,
    split_artist_album, to_price,
)


def test_clean_barcode():
    assert clean_barcode("0888751437319") == "0888751437319"
    assert clean_barcode("8 88751 43731 9") == "888751437319"
    assert clean_barcode("2000000032726") is None  # внутренний код магазина
    assert clean_barcode("143") is None
    assert clean_barcode("634904015019744861612018") is None  # два штрихкода склеены
    assert clean_barcode(None) is None
    assert barcode_key("0888751437319") == barcode_key("888751437319")


def test_detect_color():
    assert detect_color(None) == "black"
    assert detect_color("Black Vinyl LP") == "black"
    assert detect_color("Coloured Vinyl LP") == "coloured"
    assert detect_color("Limited Purple Marble Vinyl") == "splatter"
    assert detect_color("Gray With Pink & Purple Splatter") == "splatter"
    assert detect_color("Crystal Clear Vinyl") == "clear"
    assert detect_color("Translucent Red Vinyl") == "coloured"
    assert detect_color("Picture Disc") == "picture"
    assert detect_color("GOLD VINYL") == "coloured"
    assert detect_color("красный винил") == "coloured"


def test_color_part_of_title():
    assert color_part_of_title("Brockhampton – Ginger (Translucent Red Vinyl)") == "Translucent Red Vinyl"
    assert color_part_of_title("Wu-Tang Clan – Enter The Wu-Tang (36 Chambers)") is None


def test_detect_qty():
    assert detect_qty("2xVinyl, LP, Album") == 2
    assert detect_qty("Black Vinyl 2LP") == 2
    assert detect_qty("3 LP") == 3
    assert detect_qty("Vinyl, LP, Album") == 1
    assert detect_qty("CD") is None


def test_split_and_names():
    assert split_artist_album("Kendrick Lamar – good kid, m.a.a.d city (10th Anniversary)") == (
        "Kendrick Lamar", "good kid, m.a.a.d city")
    assert clean_discogs_name("Future (4)") == "Future"
    assert clean_discogs_name("Prodigy*") == "Prodigy"
    assert to_price("5490.0000") == 5490
    assert to_price("") is None


def test_pult_extract_products():
    html = 'var catalogListParams = {\n  products: [{"id":"1","name":"A [\\"x\\"]","price":{"current":3490}}],\n  foo: 1}'
    products = extract_products(html)
    assert products == [{"id": "1", "name": 'A ["x"]', "price": {"current": 3490}}]


def test_text_query_and_coverage():
    offer = {"artist_hint": "OST", "album_hint": "Euphoria (Original Score)", "raw_title": "x"}
    assert _text_query(offer) == "Euphoria"
    assert _album_coverage({"album_hint": "HUMANZ"}, "Gorillaz - G Collection") == 0
    assert _album_coverage({"album_hint": "Renegades"}, "Rage Against The Machine - Renegades") == 1


def test_master_values():
    data = {
        "title": "Autobahn", "year": 1974, "genres": ["Electronic"], "styles": ["Krautrock"],
        "artists": [{"name": "Kraftwerk", "join": "&"}, {"name": "Future (4)", "join": ""}],
        "images": [{"type": "secondary", "uri": "s"}, {"type": "primary", "uri": "p600", "uri150": "p150"}],
        "tracklist": [{"position": "", "type_": "heading", "title": "Side A"},
                      {"position": "A", "type_": "track", "title": "Autobahn", "duration": "22:43"}],
        "uri": "https://www.discogs.com/master/2994-Kraftwerk-Autobahn",
    }
    v = master_values(2994, data)
    assert v["artist_display"] == "Kraftwerk & Future"
    assert (v["cover_url"], v["cover_thumb"]) == ("p600", "p150")
    assert v["tracklist"] == [{"p": "A", "t": "Autobahn", "d": "22:43"}]
    assert v["year"] == 1974 and v["discogs_uri"].startswith("https://")
