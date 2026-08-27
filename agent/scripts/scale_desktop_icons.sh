#!/bin/bash
# Enlarge GNOME desktop icons and labels (Ubuntu 22.04 · ding extension).
set -euo pipefail

USER_NAME="${1:-youyeetoo}"
ICON_SIZE="${2:-128}"
TEXT_SCALE="${3:-2.25}"
UID_NUM="$(id -u "${USER_NAME}")"
ENV=(DISPLAY=:0 "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/${UID_NUM}/bus")

run_gs() {
  runuser -u "${USER_NAME}" -- env "${ENV[@]}" gsettings "$@"
}

echo "[desktop] icon-size=${ICON_SIZE} text-scale=${TEXT_SCALE}"

run_gs set org.gnome.desktop.interface text-scaling-factor "${TEXT_SCALE}" 2>/dev/null || true
run_gs set org.gnome.desktop.interface cursor-size "$(( ICON_SIZE / 3 ))" 2>/dev/null || true

# Desktop Icons NG (Ubuntu default)
if run_gs list-schemas 2>/dev/null | grep -q org.gnome.shell.extensions.ding; then
  run_gs set org.gnome.shell.extensions.ding icon-size "${ICON_SIZE}" 2>/dev/null || true
  run_gs set org.gnome.shell.extensions.ding text-size 14 2>/dev/null || true
fi

# Legacy nautilus desktop (harmless if absent)
run_gs set org.gnome.nautilus.desktop font-size 14 2>/dev/null || true

echo "[desktop] done (log out/in if icons unchanged)"
