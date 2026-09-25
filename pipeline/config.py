"""Настройки конвейера. Секреты берутся только из переменных окружения (или локального .env)."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    """Подхватывает app/.env для локальной разработки, не перетирая уже заданные переменные."""
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL", "")
DISCOGS_TOKEN = os.environ.get("DISCOGS_TOKEN", "")
SITE_URL = os.environ.get("GROOVE_SITE_URL", "https://disbag.github.io/groove/")
USER_AGENT = os.environ.get(
    "GROOVE_USER_AGENT",
    f"GrooveBot/0.1 (+{SITE_URL}; hobby price aggregator)",
)

# Вежливость к магазинам: не чаще одного запроса в секунду на хост.
SHOP_MIN_INTERVAL = float(os.environ.get("GROOVE_SHOP_INTERVAL", "1.0"))
# Если позиций в прогоне меньше этой доли от прошлого успешного, прогон считается подозрительным.
PARTIAL_RUN_RATIO = 0.7
# Сколько прогонов подряд позиция может отсутствовать, прежде чем стать «нет в наличии».
MISSED_RUNS_TO_OUT_OF_STOCK = 2
# Через сколько дней отсутствия позиция удаляется.
PURGE_AFTER_DAYS = 60

SCHEMA_PATH = ROOT / "db" / "schema.sql"
STATUS_PATH = ROOT / "status" / "last_run.json"
DEFAULT_EXPORT_DIR = ROOT / "web" / "public" / "data"
