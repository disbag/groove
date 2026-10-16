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
    # исполнитель — часть подписи Discogs
    ("ANDY SHEPPARD", "Romaria", "Andy Sheppard Quartet - Romaria", True),
    ("JOHN COLTRANE", "Soultrane", "John Coltrane With Red Garland - Soultrane", True),
    ("ПИКНИК", "Тень Вампира", "Пикник + Вадим Самойлов - Тень Вампира", True),
    ("NIKOLAUS HARNONCOURT", "Symphony No. 9", "Antonín Dvořák, Nikolaus Harnoncourt • Concertgebouworkest - Symphony No. 9", True),
    ("Elgar", "Enigma Variations", "Edward Elgar, London Symphony Orchestra - Enigma Variations", True),
    ("Sir Edward William Elgar, Wiener Philharmoniker", "Enigma Variations", "Elgar* - Enigma Variations", True),
    ("Future", "Hndrxx", "Future (4) - Hndrxx", True),
    ("CHICO HAMILTON / LARRY CORYELL", "The Dealer", "Chico Hamilton Introducing Larry Coryell - The Dealer", True),
    ("LEE PERRY,YOUTH", "Spaceship To Mars", "Lee Scratch Perry* & Youth - Spaceship To Mars", True),
    ("CANNED HEAT AND MEMPHIS SLIM", "Memphis Heat", "Canned Heat, Memphis Slim & The Memphis Horns - Memphis Heat", True),
    ("LOVANO, JOE / CRISPELL, MARILYN", "Trio Tapestry", "Joe Lovano, Trio Tapestry, Marilyn Crispell - Trio Tapestry", True),
    ("PETER GREEN", "Destiny Road", "Peter Green Splinter Group - Destiny Road", True),
    ("PHIL COLLINS", "A Hot Night In Paris", "The Phil Collins Big Band - A Hot Night In Paris", True),
    ("MASSIVE ATTACK", "No Protection", "Massive Attack V Mad Professor - No Protection", True),
    ("ANOHNI (ex-ANTONY & THE JOHNSONS)", "Hopelessness", "Anohni - Hopelessness", True),
    ("AVISHAI COHEN", "Into The Silence", "Avishai E. Cohen - Into The Silence", True),
    ("Various Artists", "Beetlejuice Beetlejuice", "Various - Beetlejuice Beetlejuice (Original Motion Picture Soundtrack)", True),
    # другой исполнитель, у которого в имени есть те же слова
    ("JOY", "Joy", "Joy Division - Joy", False),
    ("PRINCE", "The Truth", "Prince Jamo - The Truth", False),
    ("ALEXANDRE DESPLAT", "Harry Potter And The Deathly Hallows Part 2",
     "Alexandre Desplat - Harry Potter And The Deathly Hallows Part 1 (Original Motion Picture Soundtrack)", False),
    ("Little Big", "Greatest Hits", "Little Big Town - Greatest Hits", False),
    ("Prince Buster", "Madness", "Prince - Madness", False),
    ("Queen", "Greatest Hits", "Queen Latifah - Greatest Hits", False),
]


@pytest.mark.parametrize("artist,album,title,expected", CASES)
def test_acceptable(artist, album, title, expected):
    assert (tm.acceptable(artist, album, title) > 0) is expected


def test_split_title_fixes():
    assert split_title("Donald Byrd ‎– Byrd's Word (UK, 1956)") == ("Donald Byrd", "Byrd's Word")
    assert split_title("Big John Patton - Big John Patton - Let 'em Roll") == ("Big John Patton", "Let 'em Roll")
    assert split_title("SEX PISTOLS: SEX PISTOLS — Nevermind The Bollocks (LP)") == ("SEX PISTOLS", "Nevermind The Bollocks")
    assert split_title("ГЕННАДИЙ ГЛАДКОВ — Ты – Мне, Я – Тебе (LP)") == ("ГЕННАДИЙ ГЛАДКОВ", "Ты – Мне, Я – Тебе")
    assert split_title("THE CARDIGANS — The Rest Of The Best – Vol. 2 (2LP)") == ("THE CARDIGANS", "The Rest Of The Best – Vol. 2")


def test_exact_artist_beats_partial():
    exact = tm.acceptable("JOHN COLTRANE", "Coltrane", "John Coltrane - Coltrane")
    quartet = tm.acceptable("JOHN COLTRANE", "Coltrane", "The John Coltrane Quartet - Coltrane")
    assert exact > quartet > 0
