#!/bin/zsh
# Локальный сбор магазинов, которые не пускают серверы GitHub (сейчас — Пульт), в боевую базу Supabase.
# Подключение берётся из app/.env.production. Ночной прогон на GitHub (03:30 МСК) потом выгрузит данные на сайт.
set -euo pipefail
cd "${0:A:h}/.."
export GROOVE_ENV_FILE=.env.production
LOG="$HOME/Library/Logs/groove-local.log"
{
  echo "=== $(date '+%F %T') локальный прогон"
  .venv/bin/python -m pipeline scrape --shops "${GROOVE_LOCAL_SHOPS:-pult}"
  .venv/bin/python -m pipeline match --budget-minutes "${GROOVE_LOCAL_MATCH_MINUTES:-60}"
  echo "=== $(date '+%F %T') готово"
} >> "$LOG" 2>&1
