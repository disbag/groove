"""Приведение данных магазинов к общему виду: штрихкод, цвет винила, количество пластинок, названия."""

import html
import re
import unicodedata

_BARCODE_LENGTHS = {8, 12, 13, 14}


def clean_barcode(value) -> str | None:
    """Оставляет только цифры; отбрасывает мусор и внутренние коды магазинов (EAN-13 с префиксом 2)."""
    if value is None:
        return None
    digits = re.sub(r"\D", "", str(value))
    if len(digits) not in _BARCODE_LENGTHS:
        return None
    if len(digits) == 13 and digits.startswith("2"):
        return None  # префиксы 20–29 зарезервированы под внутренние коды магазинов
    if set(digits) == {"0"}:
        return None
    return digits


def barcode_key(digits: str) -> str:
    """Ключ сравнения: UPC-A (12 цифр) и тот же EAN-13 с ведущим нулём совпадают."""
    return digits.lstrip("0")


# Порядок важен: первое совпадение определяет класс.
_COLOR_RULES: list[tuple[str, re.Pattern]] = [
    ("picture", re.compile(r"picture[\s-]*disc|пикчер", re.I)),
    ("splatter", re.compile(
        r"splatter|сплэттер|сплаттер|marble|мрамор|swirl|galaxy|smash|nugget|tie[\s-]?dye|"
        r"haze|smoke|split|вихр|брызг", re.I)),
    ("clear", re.compile(r"\bclear\b|transparent|translucent|crystal|прозрачн", re.I)),
    ("coloured", re.compile(
        r"colou?r(ed)?\b|цветн|\b(red|blue|green|yellow|orange|pink|purple|violet|white|gold|golden|silver|"
        r"grey|gray|brown|beige|cream|bone|olive|teal|turquoise|aqua|magenta|ruby|emerald|sapphire|"
        r"milky|glow|coke bottle|sea ?glass|tangerine|lilac|lavender|mint|peach|coral|maroon|burgundy|"
        r"navy|cyan|lime|indigo|amber|opal|pearl)\b|"
        r"красн|син(ий|ем|яя|ее)|голуб|зел[её]н|ж[её]лт|оранж|розов|фиолет|\bбел(ый|ом|ая)\b|золот|серебр|"
        r"\bсер(ый|ом|ая)\b|коричн|бирюз", re.I)),
    ("black", re.compile(r"black|ч[её]рн", re.I)),
]


def detect_color(text: str | None) -> str:
    """Класс цвета по описанию издания. Чёрный — значение по умолчанию."""
    if not text:
        return "black"
    rules = dict(_COLOR_RULES)
    for name, pattern in _COLOR_RULES:
        if pattern.search(text):
            if name == "clear" and rules["coloured"].search(text):
                return "coloured"  # «Translucent Red» — всё-таки цветной
            return name
    return "black"


def color_part_of_title(title: str) -> str | None:
    """Из «Artist – Album (Limited Clear Blue Vinyl)» достаёт скобки, где описан носитель."""
    for chunk in reversed(re.findall(r"\(([^()]*)\)", title)):
        if re.search(r"vinyl|винил|\blp\b|\d\s*lp|colou?r|splatter|marble|clear|picture", chunk, re.I):
            return chunk.strip()
    return None


def edition_text(title: str) -> str | None:
    """Описание издания без исполнителя и альбома: всё в скобках плюс хвост после последней скобки.

    «Part 2: Life (2LP) Grey» → «2LP Grey». Ищем цвет только здесь: иначе Pink Floyd или
    «Purple Rain» считались бы цветным винилом.
    """
    chunks = re.findall(r"\(([^()]*)\)", title)
    tail = title.rsplit(")", 1)[1].strip() if ")" in title else ""
    text = " ".join(chunks + ([tail] if tail else [])).strip()
    return text or None


def split_title(title: str) -> tuple[str | None, str | None]:
    """«2Pac - Part 2: Life (2LP) Grey» → («2Pac», «Part 2: Life»): альбом — до первой скобки."""
    title = unescape(title)
    for sep in (" – ", " — ", " - "):
        if sep in title:
            artist, rest = title.split(sep, 1)
            artist = _dedupe_artist(artist.strip())
            # «Big John Patton - Big John Patton - Let 'em Roll»: исполнитель повторён в названии
            for sep2 in (" – ", " — ", " - "):
                if artist and rest.lower().startswith(artist.lower() + sep2):
                    rest = rest[len(artist) + len(sep2):]
            return artist or None, album_before_parentheses(rest)
    return None, album_before_parentheses(title)


def _dedupe_artist(artist: str) -> str:
    """«SEX PISTOLS: SEX PISTOLS» → «SEX PISTOLS»."""
    if ": " in artist:
        left, right = artist.split(": ", 1)
        if left.strip().lower() == right.strip().lower():
            return left.strip()
    return artist


def album_before_parentheses(text: str | None) -> str | None:
    """«Part 2: Life (2LP) Grey» → «Part 2: Life»."""
    if not text:
        return None
    return text.split("(", 1)[0].strip(" -–—") or None


_QTY_PATTERNS = [
    re.compile(r"(\d+)\s*[x×х]\s*(?:vinyl|lp|винил)", re.I),
    re.compile(r"\b(\d+)\s*-?\s*lp\b", re.I),
    re.compile(r"\b(\d+)\s*пластин", re.I),
]


def detect_qty(text: str | None) -> int | None:
    if not text:
        return None
    for pattern in _QTY_PATTERNS:
        match = pattern.search(text)
        if match:
            qty = int(match.group(1))
            if 1 <= qty <= 20:
                return qty
    if re.search(r"\blp\b|vinyl|винил", text, re.I):
        return 1
    return None


_INVISIBLE = re.compile("[\u200b-\u200f\u202a-\u202e\u2060-\u2069\ufeff]")


def unescape(text: str | None) -> str:
    """HTML-сущности, неразрывные пробелы и невидимые символы направления текста (U+200E и т. п.)."""
    text = _INVISIBLE.sub("", html.unescape(text or "")).replace("\u00a0", " ")
    return re.sub(r"\s+", " ", text).strip()


def strip_parentheses(text: str) -> str:
    return re.sub(r"\s*\([^()]*\)\s*", " ", text).strip()


def split_artist_album(title: str) -> tuple[str | None, str | None]:
    """«Artist – Album (…)» или «Artist - Album» → (artist, album)."""
    base = strip_parentheses(unescape(title))
    for sep in (" – ", " — ", " - "):
        if sep in base:
            artist, album = base.split(sep, 1)
            return artist.strip() or None, album.strip() or None
    return None, base or None


def clean_discogs_name(name: str) -> str:
    """«Future (4)» → «Future», «Prodigy*» → «Prodigy» (номера омонимов и ANV-звёздочки Discogs)."""
    name = re.sub(r"\s*\(\d+\)$", "", name.strip())
    return name.rstrip("*").strip()


def to_price(value) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(round(float(str(value).replace(" ", "").replace(",", "."))))
    except ValueError:
        return None


def fold(text: str | None) -> str:
    """Нижний регистр без диакритики: «Björk Gling-Gló» → «bjork gling-glo». Кириллицу не трогаем (кроме ё → е)."""
    text = (text or "").lower().replace("ё", "е").replace("й", "\0")
    text = "".join(ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch))
    return text.replace("\0", "й")


def title_key(text: str | None) -> str:
    """Ключ для точного сравнения названий: без регистра и диакритики, только буквы и цифры."""
    return re.sub(r"[\W_]+", "", fold(text))


_OTHER_MEDIA = re.compile(
    r"аудиокассет|кассет|cassette|\bMC\b|компакт[- ]?диск|\bCD\b|\d\s*CD\b|\bDVD\b|blu[- ]?ray|\bSACD\b", re.I)
_VINYL_MARKERS = re.compile(
    r"\bLP\b|\d\s*LP\b|\d\s*x\s*LP|vinyl|винил|\bEP\b"
    r"|(?<!\d)(7|10|12)\s*(\"|″|''|inch|дюйм|single)",  # 7", 6x7"Single, 12Single
    re.I)


def is_non_vinyl(raw_title: str | None, edition: str | None = None) -> bool:
    """Кассета, CD, DVD без винила в описании издания: «БИ-2 — Аллилуйя (Аудиокассета)».

    Смотрим только на описание издания (скобки и хвост названия + поле формата), а не на название альбома.
    Комплекты «2LP+DVD» — это винил с бонусом, их оставляем.
    """
    text = " ".join(x for x in (edition_text(raw_title or ""), (edition or "")[:300]) if x)
    return bool(_OTHER_MEDIA.search(text)) and not _VINYL_MARKERS.search(text)
