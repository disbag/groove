"""Сравнение «исполнитель + альбом» с названиями Discogs — на реальных случаях, которые раньше не находились."""

import pytest

from pipeline import textmatch as tm
from pipeline.normalize import split_title

CASES = [
    ("Deftones", "Ohms", "Deftones - _Ohms", True),
    ("PRINCE", "PURPLE RAIN", "Prince And The Revolution - Purple Rain", True),
    ("Marina", "Froot", "Marina And The Diamonds* - Froot", True),
    ("Clint Mansell", "Black Swan", "Clint Mansell - Black Swan (Original Motion Picture Soundtrack)", True),
    ("NICK CAVE / WARREN ELLIS", "Lawless", "Nick Cave & Warren Ellis - Lawless: Original Motion Picture Soundtrack", True),
    ("АРКОНА", "Слово", "Аркона - Слово = Slovo", True),
    ("ЕВГЕНИЙ КРЫЛАТОВ", "Гостья Из Будущего", "Евгений Крылатов - Гостья Из Будущего (Оригинальная Музыка К Фильму)", True),
    ("NAZARETH", "Tattoed On My Brain", "Nazareth - Tattooed On My Brain", True),
    ("Pink Floyd", "The Dark Side Of The Moon", "Pink Floyd - The Dark Side Of The Moon (50th Anniversary)", True),
    ("Various", "Hip Hop Collected", "Various - Hip Hop Collected", True),
    # не должны совпадать
    ("JAMES TAYLOR", "Greatest Hits", "James Taylor - Greatest Hits Volume 2", False),
    ("Radiohead", "Kid A", "Radiohead - Kid A Mnesia", False),
    ("Metallica", "Load", "Metallica - Reload", False),
    ("Pink Floyd", "The Dark Side Of The Moon", "Pink Floyd - The Dark Side Of The Moon Live At Wembley 1974", False),
    ("Prince", "Purple Rain", "Prince Buster - Madness", False),
    ("Various", "Dirt", "Various - Dirt", False),  # однословный сборник слишком неоднозначен
    ("OST", "A STAR IS BORN", "Judy Garland - A Star Is Born", False),
    ("Various", "The Texas Chain Saw Massacre",
     "Tobe Hooper And Wayne Bell - The Texas Chain Saw Massacre (Original Motion Picture Score)", False),
    ("OST", "Reservoir Dogs", "Various - Reservoir Dogs (Original Motion Picture Soundtrack)", True),
    ("KYLIE MINOGUE", "Disco", "Kylie* - Disco", True),
    ("ЛАДА ДЭНС", "Ночной Альбом", "Lada Dance* = Лада Дэнс - Ночной Альбом", True),
]


@pytest.mark.parametrize("artist,album,title,expected", CASES)
def test_acceptable(artist, album, title, expected):
    assert (tm.acceptable(artist, album, title) > 0) is expected


def test_split_title_fixes():
    assert split_title("Donald Byrd ‎– Byrd's Word (UK, 1956)") == ("Donald Byrd", "Byrd's Word")
    assert split_title("Big John Patton - Big John Patton - Let 'em Roll") == ("Big John Patton", "Let 'em Roll")
    assert split_title("SEX PISTOLS: SEX PISTOLS — Nevermind The Bollocks (LP)") == ("SEX PISTOLS", "Nevermind The Bollocks")
