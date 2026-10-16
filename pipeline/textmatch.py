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
# Слова состава: «The Miles Davis Quintet», «Andy Sheppard Quartet» — тот же исполнитель
_ENSEMBLE = {
    "quartet", "quintet", "trio", "sextet", "septet", "octet", "nonet", "orchestra", "band", "group", "ensemble",
    "experience", "symphony", "philharmonic", "chamber", "chorus", "choir", "singers", "strings",
    "квартет", "квинтет", "трио", "оркестр", "ансамбль", "группа", "хор",
}
# Связки в подписях исполнителей — не часть имени: «Ian Carr With Nucleus», «Byron Janis Plays Mussorgsky»
_LINKS = {
    "with", "featuring", "feat", "ft", "vs", "v", "presents", "present", "introducing", "meets", "plays", "narrates",
    "performed", "performs", "perform", "by", "plus", "x", "e", "y", "et", "und", "his", "her", "their", "collaboration",
}
_ARTIST_SMALL = _SMALL | _LINKS
# Разделители исполнителей в подписи: «Prince And The Revolution», «Nick Cave & Warren Ellis», «Lada Dance = Лада Дэнс»
_CONNECTORS = re.compile(
    r"\s+(?:and|with|in collaboration with|featuring|feat\.?|ft\.?|vs\.?|v|presents?|introducing|meets|plays"
    r"|narrates|performed by|performs?|plus|x|e|y|et|und|и)\s+|\s+-\s+|\s*[,;&/+=•·*]\s*",
    re.I,
)
# Пояснения в скобках: номер омонима Discogs «Future (4)», «ANOHNI (ex-ANTONY & THE JOHNSONS)»
_ARTIST_NOTE = re.compile(r"\([^()]*\)")
_BIG_BAND = re.compile(r"\bbig band\b", re.I)


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
    """1.0 — тот же исполнитель; 0.9–0.95 — один из исполнителей подписи; меньше 0.85 — другой исполнитель.

    Вхождение слов само по себе ничего не значит: «Little Big» ⊂ «Little Big Town», «Prince» ⊂ «Prince Buster».
    Засчитываем, только если каждое слово объясняется целым исполнителем подписи или его фамилией.
    """
    q = _artist_words(query)
    r = _artist_words(result)
    if not q or not r:
        return 0.0
    if q == r:
        return 1.0  # «Nick Cave / Warren Ellis» = «Nick Cave & Warren Ellis», «Ian Carr With Nucleus (3)»
    if q < r:
        return 0.95 if _covered(q, result or "") else 0.6  # «Prince» в «Prince And The Revolution»
    if r < q:
        if "*" in (result or "") or _covered(r, query or ""):
            return 0.9  # вариант имени Discogs «Kylie*»; «Elgar» из «Sir Edward William Elgar, Wiener …»
        return 0.6
    return ratio(query or "", result or "")


def other_artist(query: str | None, result: str | None) -> bool:
    """Подпись содержит слова исполнителя, но это другой исполнитель: «Little Big» и «Little Big Town»."""
    if is_compilation(query) or is_compilation(result):
        return False
    q, r = _artist_words(query), _artist_words(result)
    return bool(q and r) and (q < r or r < q) and artist_score(query, result) < ACCEPT


def _clean_artist(text: str | None) -> str:
    text = _ARTIST_NOTE.sub(" ", _ARTIST_NOTE.sub(" ", text or ""))  # дважды — для вложенных скобок
    return _BIG_BAND.sub("band", text)


def _artist_words(text: str | None) -> set[str]:
    return set(words(_clean_artist(text))) - _ARTIST_SMALL


def _covered(names: set[str], text: str) -> bool:
    """Каждое из слов names объясняется исполнителем из подписи text, который:
    - целиком состоит из этих слов: «John Coltrane» в «The John Coltrane Quartet»;
    - кончается на одно из них, то есть на фамилию: «Elgar» в «Sir Edward Elgar», «Lee Perry» в «Lee Scratch Perry»;
    - или называет коллектив исполнителя: «Peter Green» в «Peter Green Splinter Group»."""
    names = names - _ENSEMBLE
    covered: set[str] = set()
    for part in _CONNECTORS.split(_clean_artist(text)):
        raw = [w for w in words(part) if w not in _ARTIST_SMALL]
        seg = [w for w in raw if w not in _ENSEMBLE]
        if not seg:
            continue
        own_band = raw[-1] in _ENSEMBLE and len(seg) > len(names) and set(seg[:len(names)]) == names
        if set(seg) <= names or seg[-1] in names or own_band:
            covered |= set(seg) & names
    return bool(names) and names <= covered


def album_score(query: str | None, result: str | None, subtitle: str | None = None) -> float:
    q = set(words(query)) - _SMALL
    if not q:
        return 0.0
    full = set(words(result))
    if not q <= full:
        if any(_EDITION_MARKERS.match(w) for w in q - full):
            return 0.5  # «Part 2» ≠ «Part 1»: похожие строки, но другой том
        return ratio(query or "", album_core(result or ""))  # опечатки: «Tattoed» ~ «Tattooed»
    # слова из скобок магазина — не лишние: «Madame X (Music From The Theater Experience)»
    extra = set(words(album_core(result or ""))) - q - _SMALL - _SOUNDTRACK - _DESCRIPTORS - set(words(subtitle))
    if any(_EDITION_MARKERS.match(w) for w in extra):
        return 0.5  # другой том / часть
    # любое другое лишнее слово — скорее другой альбом: «Kid A» ≠ «Kid A Mnesia»
    return len(q) / (len(q) + len(extra))


def score(artist: str | None, album: str | None, result_title: str) -> tuple[float, float]:
    """Оценка по названию из поиска Discogs «Artist - Title»."""
    return score_parts(artist, album, *split_result_title(result_title))


def score_parts(artist: str | None, album: str | None, r_artist: str, r_album: str,
                subtitle: str | None = None) -> tuple[float, float]:
    """Оценка по исполнителю и альбому Discogs по отдельности (в подписи бывает « - »: «Henry Purcell - Alfred Deller»)."""
    if is_compilation(artist) or not artist:
        # сборник должен совпасть со сборником: «OST — A Star Is Born» ≠ «Judy Garland — A Star Is Born»
        a = 1.0 if is_compilation(r_artist) else 0.0
    else:
        a = artist_score(artist, r_artist)
    return a, album_score(album, r_album, subtitle)


def acceptable(artist: str | None, album: str | None, result_title: str, subtitle: str | None = None) -> float:
    """Итоговая оценка совпадения с названием из поиска Discogs (0, если не принимаем)."""
    return acceptable_parts(artist, album, *split_result_title(result_title), subtitle=subtitle)


def acceptable_parts(artist: str | None, album: str | None, r_artist: str, r_album: str,
                     subtitle: str | None = None) -> float:
    """subtitle — текст из скобок в названии магазина, похожий на часть названия, а не на описание издания.
    Альбом, в названии которого он есть, получает преимущество: «Madame X» и «Madame X: Music From
    The Theater Experience» для позиции «Madame X (Music From The Theater Experience)»."""
    a, b = score_parts(artist, album, r_artist, r_album, subtitle)
    if a < ACCEPT or b < ACCEPT:
        return 0.0
    # для сборников и безымянных исполнителей однословные альбомы слишком неоднозначны
    if (is_compilation(artist) or not artist) and len([w for w in words(album) if w not in _SMALL]) < 2:
        return 0.0
    return a + b + 0.1 * subtitle_coverage(subtitle, r_album)


def subtitle_coverage(subtitle: str | None, result_album: str | None) -> float:
    """Доля слов подзаголовка из скобок, которые есть в названии альбома Discogs."""
    wanted = set(words(subtitle)) - _SMALL
    return len(wanted & set(words(result_album))) / len(wanted) if wanted else 0.0
