from pipeline.export import _artists, artist_letter, artist_slug


def test_artist_slug():
    assert artist_slug("Björk") == "bjork"
    assert artist_slug("AC/DC") == "ac-dc"
    assert artist_slug("Кино") == "кино"
    assert artist_slug("Мумий Тролль") == "мумий-тролль"
    long = artist_slug("Пётр Ильич Чайковский, Государственный академический симфонический оркестр СССР, Евгений Светланов")
    assert len(long.encode()) <= 120 and long != artist_slug("Пётр Ильич Чайковский, Другой оркестр, Другой дирижёр")


def test_artist_letter():
    assert artist_letter("The Beatles") == "B"
    assert artist_letter("Кино") == "К"
    assert artist_letter("Ёлка") == "Е"  # ё сортируется как е
    assert artist_letter("2Pac") == "#"
    assert artist_letter("Ænigmatum") == "Æ"
    assert artist_letter("'Baby Face' Willette") == "B"
    assert artist_letter("*NSYNC") == "N"
    assert artist_letter("Björk") == "B"
    assert artist_letter("장기하와 얼굴들") == "장"


def test_artists_groups_spellings_and_skips_compilations():
    cards = [
        {"id": 1, "artist_display": "AC/DC", "title": "Back In Black", "min_price": 5000},
        {"id": 2, "artist_display": "AC/DC", "title": "Highway To Hell", "min_price": 4000},
        {"id": 3, "artist_display": "Ac-Dc", "title": "Powerage", "min_price": 4500},
        {"id": 4, "artist_display": "Various", "title": "Hits", "min_price": 2000},
        {"id": 5, "artist_display": "Кино", "title": "Группа Крови", "min_price": 3000},
        {"id": 6, "artist_display": "Кино = Кино", "title": "Звезда", "min_price": 3500},
    ]
    artists = _artists(cards)
    assert [(a["slug"], a["name"], len(a["cards"]), a["min_price"]) for a in artists] == [
        ("ac-dc", "AC/DC", 3, 4000), ("кино", "Кино", 2, 3000)]
    assert [c["artist_slug"] for c in cards] == ["ac-dc", "ac-dc", "ac-dc", None, "кино", "кино"]
