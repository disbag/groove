"""Клиент Discogs API с соблюдением лимита: 60 запросов/мин с токеном, 25 без него."""

import logging
import time

import requests

from . import config

log = logging.getLogger(__name__)
API = "https://api.discogs.com"


class Discogs:
    def __init__(self, token: str = config.DISCOGS_TOKEN):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = config.USER_AGENT
        if token:
            self.session.headers["Authorization"] = f"Discogs token={token}"
        self.interval = 60 / (60 if token else 25) + 0.05
        self._last = 0.0
        self.calls = 0

    def _get(self, path: str, params: dict | None = None) -> dict | None:
        for attempt in range(5):
            wait = self.interval - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            self.calls += 1
            try:
                response = self.session.get(f"{API}{path}", params=params, timeout=30)
            except requests.RequestException as exc:
                log.warning("Discogs %s: %s, повтор", path, exc)
                time.sleep(5 * (attempt + 1))
                continue
            if response.status_code == 429:
                log.warning("Discogs: превышен лимит, пауза 60 с")
                time.sleep(60)
                continue
            if response.status_code == 404:
                return None
            if response.status_code >= 500:
                time.sleep(5 * (attempt + 1))
                continue
            response.raise_for_status()
            remaining = int(response.headers.get("x-discogs-ratelimit-remaining", "10"))
            if remaining <= 1:
                time.sleep(30)  # окно лимита скользящее; даём ему освободиться
            return response.json()
        raise RuntimeError(f"Discogs {path}: не удалось получить ответ")

    def search_barcode(self, barcode: str) -> list[dict]:
        data = self._get("/database/search", {"barcode": barcode, "type": "release", "per_page": 50})
        return (data or {}).get("results", [])

    def search_vinyl_releases(self, query: str) -> list[dict]:
        data = self._get("/database/search", {"q": query, "type": "release", "format": "Vinyl", "per_page": 25})
        return (data or {}).get("results", [])

    def master(self, master_id: int) -> dict | None:
        return self._get(f"/masters/{master_id}")

    def release(self, release_id: int) -> dict | None:
        return self._get(f"/releases/{release_id}")
