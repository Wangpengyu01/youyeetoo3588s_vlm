#!/bin/bash
# GNOME login autostart — open 小揽 GUI after desktop is ready.
set -euo pipefail

AGENT_ROOT="${AGENT_ROOT:-/userdata/agent}"
USER_NAME="${USER:-youyeetoo}"
UID_NUM="$(id -u "${USER_NAME}" 2>/dev/null || echo 1000)"

export DISPLAY="${DISPLAY:-:0}"
export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=/run/user/${UID_NUM}/bus}"

for _ in $(seq 1 90); do
  pgrep -u "${USER_NAME}" -x gnome-shell >/dev/null 2>&1 && break
  sleep 1
done
sleep 4

if pgrep -u "${USER_NAME}" -f "chromium.*8766" >/dev/null 2>&1; then
  echo "[autostart-gui] already running"
  exit 0
fi

exec /bin/bash "${AGENT_ROOT}/scripts/open_agent_gui.sh"
