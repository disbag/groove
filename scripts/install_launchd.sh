#!/bin/zsh
# Ставит ежедневный запуск scripts/local_run.sh через launchd (по умолчанию в 02:30 — до ночного прогона на GitHub).
# Если Mac в это время спит, launchd запустит задачу после пробуждения. Удалить: scripts/install_launchd.sh --remove
set -euo pipefail
APP="${0:A:h:h}"
LABEL="ru.groove.local"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
if [[ "${1:-}" == "--remove" ]]; then
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  rm -f "$PLIST"
  echo "запуск удалён"
  exit 0
fi
cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array><string>/bin/zsh</string><string>$APP/scripts/local_run.sh</string></array>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>${GROOVE_HOUR:-2}</integer><key>Minute</key><integer>${GROOVE_MINUTE:-30}</integer></dict>
  <key>StandardOutPath</key><string>$HOME/Library/Logs/groove-local.launchd.log</string>
  <key>StandardErrorPath</key><string>$HOME/Library/Logs/groove-local.launchd.log</string>
</dict>
</plist>
PLIST
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "ежедневный запуск установлен: $PLIST"
