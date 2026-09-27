"""Сравнение «исполнитель + альбом» из магазина с названием Discogs «Artist - Title».

Исполнитель и альбом оцениваются отдельно, потому что Discogs оформляет названия иначе, чем магазины:
расширенные подписи исполнителя («Prince And The Revolution», «Marina And The Diamonds*»), приписки к альбому
(«(Original Motion Picture Soundtrack)», «= Slovo»), стилизация («_Ohms»).
"""

import re
from difflib import SequenceMatcher

from .normalize import fold

ACCEPT = 0.85
COMPILATION_ARTISTS = {"ost", "v/a", "va", "сборник", "various", "various artists", "саундтрек", "soundtrack"}
_SMALL = {"the", "a", "an", "and", "of", "lp", "vinyl", "&", "и"}
# Слова приписок к саундтрекам: не считаются «лишними» в названии Discogs
_SOUNDTRACK = {
    "original", "motion", "picture", "soundtrack", "ost", "music", "from", "film", "score", "series", "netflix",
    "hbo", "inspired", "by", "songs", "оригинальная", "музыка", "к", "фильму", "саундтрек", "из", "кинофильма",
    "фильма", "мультфильма",
}
# Описания издания: могут стоять в названии Discogs и не делают альбом другим
_DESCRIPTORS = {
    "deluxe", "remastered", "remaster", "anniversary", "edition", "expanded", "reissue", "version", "special",
    "limited", "bonus", "tracks", "collectors", "collector", "th", "st", "nd", "rd", "издание", "ремастер",
}
# Лишние слова такого вида означают другое издание: «Greatest Hits» ≠ «Greatest Hits Vol. 2»
_EDITION_MARKERS = re.compile(r"^(\d+|vol|volume|part|pt|ii|iii|iv|v|vi|chapter|том|часть)$")


def words(text: str | None) -> list[str]:
    """Слова без регистра и диакритики, только буквы и цифры: «_Ohms» → ["ohms"]."""
    return re.findall(r"[^\W_]+", fold(text))


def is_compilation(artist: str | None) -> bool:
    return (artist or "").strip().lower() in COMPILATION_ARTISTS


def split_result_title(title: str) -> tuple[str, str]:
    """«Artist - Title» из поиска Discogs → (artist, title)."""
    if " - " in title:
        artist, album = title.split(" - ", 1)
        return artist, album
    return "", title


def album_core(album: str) -> str:
    """Название без приписок: до « = » (параллельное название) и до первой скобки."""
    album = album.split(" = ", 1)[0]
    return re.split(r"[(\[]", album, maxsplit=1)[0].strip()


def ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, " ".join(sorted(words(a))), " ".join(sorted(words(b)))).ratio()


def artist_score(query: str | None, result: str | None) -> float:
    """1.0 — исполнитель из магазина целиком входит в подпись Discogs (или наоборот, для классики)."""
    q = set(words(query)) - _SMALL
    r = set(words(result)) - _SMALL
    if not q or not r:
        return 0.0
    if q <= r:
        return 1.0  # «Prince» ⊂ «Prince And The Revolution», «Nick Cave / Warren Ellis» = «Nick Cave & Warren Ellis»
    if r <= q:
        return 0.9  # «Sir Edward William Elgar, Wiener Philharmoniker» ⊃ «Elgar»
    return ratio(query or "", result or "")


def album_score(query: str | None, result: str | None) -> float:
    q = set(words(query)) - _SMALL
    if not q:
        return 0.0
    full = set(words(result))
    if not q <= full:
        return ratio(query or "", album_core(result or ""))  # опечатки: «Tattoed» ~ «Tattooed»
    extra = set(words(album_core(result or ""))) - q - _SMALL - _SOUNDTRACK - _DESCRIPTORS
    if any(_EDITION_MARKERS.match(w) for w in extra):
        return 0.5  # другой том / часть
    # любое другое лишнее слово — скорее другой альбом: «Kid A» ≠ «Kid A Mnesia»
    return len(q) / (len(q) + len(extra))


def score(artist: str | None, album: str | None, result_title: str) -> tuple[float, float]:
    r_artist, r_album = split_result_title(result_title)
    if is_compilation(artist) or not artist:
        # сборник должен совпасть со сборником: «OST — A Star Is Born» ≠ «Judy Garland — A Star Is Born»
        a = 1.0 if is_compilation(r_artist) else 0.0
    else:
        a = artist_score(artist, r_artist)
    return a, album_score(album, r_album)


def acceptable(artist: str | None, album: str | None, result_title: str) -> float:
    """Итоговая оценка совпадения (0, если не принимаем)."""
    a, b = score(artist, album, result_title)
    if a < ACCEPT or b < ACCEPT:
        return 0.0
    # для сборников и безымянных исполнителей однословные альбомы слишком неоднозначны
    if (is_compilation(artist) or not artist) and len(set(words(album)) - _SMALL) < 2:
        return 0.0
    return a + b
