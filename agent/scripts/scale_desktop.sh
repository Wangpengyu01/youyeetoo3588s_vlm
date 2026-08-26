#!/bin/bash
# Enlarge GNOME desktop — HDMI only (R1 Ubuntu 22.04, no DSI panel)
# Usage: scale_desktop.sh [text_scale] [ui_scale]
export DISPLAY=:0
export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus

TEXT_SCALE="${1:-2.0}"
UI_SCALE="${2:-2.0}"
MONITORS="${HOME}/.config/monitors.xml"
CURSOR=$(( ${TEXT_SCALE%.*} * 24 ))
[ "$CURSOR" -lt 32 ] && CURSOR=32
[ "$CURSOR" -gt 64 ] && CURSOR=64

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "${SCRIPT_DIR}/display_hdmi_only.sh"

gsettings set org.gnome.mutter experimental-features "['scale-monitor-framebuffer']"
gsettings set org.gnome.desktop.interface text-scaling-factor "$TEXT_SCALE"
gsettings set org.gnome.desktop.interface cursor-size "$CURSOR"

if [ -f "${SCRIPT_DIR}/monitors_hdmi_only.xml" ]; then
  cp -a "$MONITORS" "${MONITORS}.bak" 2>/dev/null || true
  cp "${SCRIPT_DIR}/monitors_hdmi_only.xml" "$MONITORS"
  sed -i "s|<scale>2.0</scale>|<scale>${UI_SCALE}</scale>|" "$MONITORS"
elif [ -f "$MONITORS" ]; then
  cp -a "$MONITORS" "${MONITORS}.bak"
  sed -i '/DSI-1/,/<\/logicalmonitor>/d' "$MONITORS"
  sed -i "s|<scale>[0-9.]*</scale>|<scale>${UI_SCALE}</scale>|g" "$MONITORS"
fi

echo "text-scaling-factor: $(gsettings get org.gnome.desktop.interface text-scaling-factor)"
echo "cursor-size: $(gsettings get org.gnome.desktop.interface cursor-size)"
echo "ui-scale: ${UI_SCALE} (HDMI-1 only, DSI off)"
echo "Tip: log out and back in once for full icon/window scale."
