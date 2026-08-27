#!/bin/bash
# Open local agent control panel in the default browser.
set -euo pipefail

AGENT_ROOT="${AGENT_ROOT:-/userdata/agent}"
UI_DIR="${AGENT_ROOT}/ui"
PORT="${AGENT_GUI_PORT:-8766}"
PIDFILE="${AGENT_ROOT}/run/gui_http.pid"
LOG="${AGENT_ROOT}/logs/gui_http.log"
URL="http://127.0.0.1:${PORT}/"

notify() {
  local msg="$1"
  if command -v notify-send >/dev/null 2>&1 && [[ -n "${DISPLAY:-}" ]]; then
    notify-send "小揽语音助手" "$msg" 2>/dev/null || true
  fi
  echo "[gui] ${msg}" >&2
}

mkdir -p "${AGENT_ROOT}/run" "${AGENT_ROOT}/logs"

if pgrep -u "${USER:-youyeetoo}" -f "chromium.*${PORT}" >/dev/null 2>&1; then
  echo "[gui] already running"
  exit 0
fi

if [[ ! -f "${UI_DIR}/index.html" ]]; then
  notify "缺少界面文件，请重新部署 agent"
  exit 1
fi

port_listening() {
  python3 - <<PY
import socket
s = socket.socket()
try:
    s.settimeout(0.5)
    s.connect(("127.0.0.1", ${PORT}))
    print("yes")
except OSError:
    print("no")
finally:
    s.close()
PY
}

start_http() {
  if [[ "$(port_listening)" == "yes" ]]; then
    return 0
  fi
  if [[ -f "${PIDFILE}" ]]; then
    old_pid="$(cat "${PIDFILE}")"
    if kill -0 "${old_pid}" 2>/dev/null; then
      kill "${old_pid}" 2>/dev/null || true
      sleep 0.2
    fi
    rm -f "${PIDFILE}"
  fi
  nohup python3 -m http.server "${PORT}" --bind 127.0.0.1 --directory "${UI_DIR}" >>"${LOG}" 2>&1 &
  echo $! >"${PIDFILE}"
  sleep 0.4
  if [[ "$(port_listening)" != "yes" ]]; then
    notify "控制面板 HTTP 服务启动失败，见 ${LOG}"
    exit 1
  fi
}

open_browser() {
  local flags=(
    --app="${URL}"
    --start-fullscreen
    --no-first-run
    --disable-infobars
    --disable-session-crashed-bubble
    --disable-translate
    --noerrdialogs
  )
  # R1 官方镜像：firefox 是 snap 占位包，xdg-open 会失败；chromium-x11 可用
  if [[ -x /usr/bin/chromium ]]; then
    /usr/bin/chromium "${flags[@]}" >/dev/null 2>&1 &
    return 0
  fi
  if command -v chromium-browser >/dev/null 2>&1; then
    chromium-browser "${flags[@]}" >/dev/null 2>&1 &
    return 0
  fi
  if command -v firefox >/dev/null 2>&1 && ! firefox --version 2>&1 | grep -qi snap; then
    firefox --new-window "${URL}" >/dev/null 2>&1 &
    return 0
  fi
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "${URL}" >/dev/null 2>&1 &
    return 0
  fi
  return 1
}

start_http
if open_browser; then
  echo "[gui] opened ${URL}"
else
  notify "未找到可用浏览器，请手动打开 ${URL}"
  exit 1
fi
