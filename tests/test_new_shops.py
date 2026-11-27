from types import SimpleNamespace

import pytest

from pipeline.adapters import doctorhead, respublica


@pytest.mark.parametrize(
    "shop,param,pager,card",
    [
        (doctorhead, "PAGEN_1", "pagination-list__item", """
          <div class="catalog-list__item" data-element-id="{id}">
            <a class="product-descr__link" href="/product/test/">
              <span class="product-descr__title">Artist – Album (Red) 2LP</span>
            </a>
            <div class="product-price" data-price="4690"><s>5990</s></div>
            <div class="product-status">{stock}</div>
          </div>
        """),
        (respublica, "page", "pages-item-link", """
          <main><div itemtype="https://schema.org/Product">
            <meta itemprop="sku" content="{id}">
            <h3><a href="/muzyka-na-vinile/vinilovye-plastinki/test">Artist – Album (Red) 2LP</a></h3>
            <meta itemprop="price" content="4690">
            <meta itemprop="availability" content="https://schema.org/{stock}">
          </div></main>
        """),
    ],
)
def test_catalog_pagination_and_offer_fields(shop, param, pager, card):
    listed, unavailable = ("В наличии", "На заказ") if shop is doctorhead else ("InStock", "OutOfStock")
    first = card.format(id=1, stock=listed) + f'<a class="{pager}" href="?{param}=2">2</a>'
    second = card.format(id=2, stock=unavailable)

    class Catalog:
        def __init__(self, pages):
            self.pages = iter(pages)
            self.params = []

        def get(self, url, params=None):
            assert url == shop.LISTING
            self.params.append(params)
            return SimpleNamespace(text=next(self.pages))

    http = Catalog([first, second])
    sections = {}
    offers = shop.fetch(http, sections=sections)
    assert http.params == [None, {param: 2}]
    assert sections == {shop.LISTING: "последняя страница (2)"}
    assert [offer.external_id for offer in offers] == ["1", "2"]
    assert [offer.in_stock for offer in offers] == [True, False]
    assert (offers[0].price, offers[0].artist_hint, offers[0].album_hint, offers[0].format_qty) == (
        4690, "Artist", "Album", 2,
    )

    with pytest.raises(ValueError, match="нет новых карточек"):
        shop.fetch(Catalog([first, first]))
