"""Локальный PostgreSQL для разработки (пакет pgserver): печатает строку подключения для app/.env.

    pip install -r requirements-dev.txt
    python scripts/dev_db.py        # держите процесс запущенным, пока идёт разработка
"""

import time
from pathlib import Path

import pgserver

data = Path(__file__).resolve().parent.parent / ".pgdata"
server = pgserver.get_server(data, cleanup_mode="stop")
print(f"DATABASE_URL={server.get_uri()}", flush=True)
try:
    while True:
        time.sleep(3600)
except KeyboardInterrupt:
    pass
