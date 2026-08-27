#!/bin/bash
# GNOME login autostart — open 小揽 GUI after desktop + orchestrator are ready.
set -euo pipefail

AGENT_ROOT="${AGENT_ROOT:-/userdata/agent}"
USER_NAME="${USER:-youyeetoo}"
UID_NUM="$(id -u "${USER_NAME}" 2>/dev/null || echo 1000)"
LOG="${AGENT_ROOT}/logs/gui_autostart.log"

export DISPLAY="${DISPLAY:-:0}"
export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=/run/user/${UID_NUM}/bus}"

log() {
  echo "[autostart-gui] $*" | tee -a "${LOG}" >&2
}

log "starting (user=${USER_NAME} display=${DISPLAY})"

for _ in $(seq 1 90); do
  pgrep -u "${USER_NAME}" -x gnome-shell >/dev/null 2>&1 && break
  sleep 1
done
sleep 4

wait_for_orchestrator() {
  local port="${AGENT_WS_PORT:-8765}"
  for _ in $(seq 1 120); do
    if python3 - <<PY 2>/dev/null
import socket
s = socket.socket()
s.settimeout(0.5)
s.connect(("127.0.0.1", ${port}))
s.close()
PY
    then
      log "orchestrator ready on ${port}"
      return 0
    fi
    sleep 1
  done
  log "WARN: orchestrator not ready after 120s"
  return 1
}

wait_for_orchestrator || true

exec /bin/bash "${AGENT_ROOT}/scripts/open_agent_gui.sh"
