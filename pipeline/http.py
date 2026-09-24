"""HTTP-клиент для магазинов: свой User-Agent, повторы и пауза между запросами к одному хосту."""

import time
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from . import config


class PoliteSession:
    def __init__(self, min_interval: float = config.SHOP_MIN_INTERVAL, timeout: float = 30):
        self.min_interval = min_interval
        self.timeout = timeout
        self._last: dict[str, float] = {}
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": config.USER_AGENT,
            "Accept-Language": "ru-RU,ru;q=0.9",
        })
        retry = Retry(
            total=4,
            backoff_factor=3,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
            respect_retry_after_header=True,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def get(self, url: str, **kwargs) -> requests.Response:
        host = urlparse(url).netloc
        wait = self.min_interval - (time.monotonic() - self._last.get(host, 0.0))
        if wait > 0:
            time.sleep(wait)
        try:
            response = self.session.get(url, timeout=self.timeout, **kwargs)
        finally:
            self._last[host] = time.monotonic()
        response.raise_for_status()
        return response
