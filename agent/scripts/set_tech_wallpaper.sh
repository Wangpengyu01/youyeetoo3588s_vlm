#!/bin/bash
# Set tech-style desktop wallpaper for GNOME session.
set -euo pipefail

AGENT_ROOT="${AGENT_ROOT:-/userdata/agent}"
USER_NAME="${1:-youyeetoo}"
WALL="${AGENT_ROOT}/ui/wallpaper.svg"
UID_NUM="$(id -u "${USER_NAME}")"
ENV=(DISPLAY=:0 "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/${UID_NUM}/bus")

if [[ ! -f "${WALL}" ]]; then
  echo "[wallpaper] missing ${WALL}" >&2
  exit 1
fi

URI="file://${WALL}"

run_gs() {
  runuser -u "${USER_NAME}" -- env "${ENV[@]}" gsettings "$@"
}

run_gs set org.gnome.desktop.background picture-uri "'${URI}'" 2>/dev/null || true
run_gs set org.gnome.desktop.background picture-uri-dark "'${URI}'" 2>/dev/null || true
run_gs set org.gnome.desktop.background picture-options "'zoom'" 2>/dev/null || true
run_gs set org.gnome.desktop.background primary-color "'#0f1419'" 2>/dev/null || true
run_gs set org.gnome.desktop.screensaver picture-uri "'${URI}'" 2>/dev/null || true

echo "[wallpaper] set ${WALL}"
