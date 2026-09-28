#!/bin/bash
set -euo pipefail
USB_CONN="${RNDIS_NM_CONN:-r1-rndis-usb}"
USB_IF="${RNDIS_IF:-usb0}"
if [ ! -d "/sys/class/net/${USB_IF}" ]; then
  echo "[rndis-boot] ${USB_IF} absent — skip"
  exit 0
fi
nmcli con up "${USB_CONN}" 2>/dev/null || bash /userdata/p4/scripts/install_rndis_usb.sh
