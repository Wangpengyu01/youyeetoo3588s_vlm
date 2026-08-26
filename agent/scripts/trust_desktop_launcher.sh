#!/bin/bash
# Mark desktop launchers as trusted (GNOME requires this before double-click runs).
set -euo pipefail
USER_NAME="${1:-youyeetoo}"
USER_HOME="$(getent passwd "${USER_NAME}" | cut -d: -f6)"
DESKTOP_DIR="${USER_HOME}/Desktop"

export DISPLAY=:0
export DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$(id -u "${USER_NAME}")/bus"

for f in "${DESKTOP_DIR}"/*.desktop; do
  [[ -f "$f" ]] || continue
  chmod 755 "$f"
  chown "${USER_NAME}:${USER_NAME}" "$f"
  if command -v gio >/dev/null 2>&1; then
    if id "${USER_NAME}" >/dev/null 2>&1; then
      runuser -u "${USER_NAME}" -- env DISPLAY=:0 DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$(id -u "${USER_NAME}")/bus" \
        gio set "$f" metadata::trusted true 2>/dev/null || true
    fi
  fi
  echo "[desktop] trusted $(basename "$f")"
done

echo "[desktop] trusted launchers in ${DESKTOP_DIR}"
