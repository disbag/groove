"""Реестр адаптеров магазинов. Новый магазин = модуль с SHOP и fetch(http) -> list[Offer]."""

from . import korobka, pult, stoprobot

ADAPTERS = {module.SHOP.code: module for module in (stoprobot, korobka, pult)}
