"""Реестр адаптеров магазинов. Новый магазин = модуль с SHOP и fetch(http) -> list[Offer]."""

from . import (
    doctorhead, korobka, newartstore, plstkwrld, pult, respublica, sferazvyka, stereozona, stoprobot, vidika, vinylis,
)

ADAPTERS = {
    module.SHOP.code: module
    for module in (stoprobot, korobka, pult, vinylis, plstkwrld, newartstore, vidika, stereozona, sferazvyka, doctorhead, respublica)
}
