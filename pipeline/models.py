from dataclasses import dataclass


@dataclass
class Offer:
    """Нормализованная позиция магазина — то, что возвращает любой адаптер."""

    external_id: str
    url: str
    raw_title: str
    price: int | None
    in_stock: bool
    barcode: str | None = None
    artist_hint: str | None = None
    album_hint: str | None = None
    color: str = "black"
    color_raw: str | None = None
    format_qty: int | None = None
    image_url: str | None = None


@dataclass(frozen=True)
class Shop:
    code: str
    name: str
    base_url: str
    adapter: str
