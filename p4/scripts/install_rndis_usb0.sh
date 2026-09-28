#!/bin/bash
# USB RNDIS/usb0 for PC maintenance while eth0 stays on camera LAN (192.168.2.x).
# Run on board as root: sudo bash /userdata/p4/scripts/install_rndis_usb0.sh
set -euo pipefail
P4_ROOT="${P4_ROOT:-/userdata/p4}"
# Must NOT overlap eth0 camera subnet (see p4_env STATIC_IP)
USB_IF="${RNDIS_IF:-usb0}"
USB_CONN="${RNDIS_NM_CONN:-r1-rndis-usb}"
USB_IP="${RNDIS_IP:-192.168.7.1}"
USB_PREFIX="${RNDIS_PREFIX:-24}"
USB_CIDR="${USB_IP}/${USB_PREFIX}"
# shared = DHCP for PC; manual = fixed board IP only
USB_METHOD="${RNDIS_METHOD:-shared}"

if [ ! -d "/sys/class/net/${USB_IF}" ]; then
  echo "[rndis] no ${USB_IF} — plug USB to PC, enable gadget RNDIS, then retry" >&2
  echo "[rndis] interfaces:" >&2
  ls -1 /sys/class/net/ >&2 || true
  exit 1
fi

# NetworkManager sometimes marks USB gadget unmanaged
if [ -f /etc/udev/rules.d/85-nm-unmanaged.rules ]; then
  sed -i 's/ENV{DEVTYPE}=="gadget", ENV{NM_UNMANAGED}="1"/ENV{DEVTYPE}=="gadget", ENV{NM_UNMANAGED}="0"/' \
    /etc/udev/rules.d/85-nm-unmanaged.rules 2>/dev/null || true
  udevadm control --reload-rules 2>/dev/null || true
fi

echo "[rndis] ${USB_IF} → ${USB_CIDR} method=${USB_METHOD} conn=${USB_CONN}"

if nmcli -t -f NAME con show 2>/dev/null | grep -Fxq "${USB_CONN}"; then
  nmcli con mod "${USB_CONN}" \
    connection.interface-name "${USB_IF}" \
    connection.autoconnect yes \
    ipv4.method "${USB_METHOD}" \
    ipv6.method disabled \
    ipv4.route-metric 200 \
    ipv4.dns-priority 200
  if [ "${USB_METHOD}" = "manual" ]; then
    nmcli con mod "${USB_CONN}" ipv4.addresses "${USB_CIDR}" ipv4.gateway ""
  fi
else
  if [ "${USB_METHOD}" = "shared" ]; then
    nmcli con add type ethernet ifname "${USB_IF}" con-name "${USB_CONN}" autoconnect yes \
      ipv4.method shared ipv6.method disabled \
      ipv4.route-metric 200 ipv4.dns-priority 200
  else
    nmcli con add type ethernet ifname "${USB_IF}" con-name "${USB_CONN}" autoconnect yes \
      ipv4.method manual ipv4.addresses "${USB_CIDR}" ipv6.method disabled \
      ipv4.route-metric 200 ipv4.dns-priority 200
  fi
fi

nmcli con down "${USB_CONN}" 2>/dev/null || true
sleep 1
nmcli con up "${USB_CONN}"

echo "[rndis] active:"
nmcli -f GENERAL.STATE,IP4.ADDRESS dev show "${USB_IF}" 2>/dev/null || ip -br addr show "${USB_IF}"
echo "[rndis] PC: USB RNDIS adapter → DHCP or static 192.168.7.x/24, ping ${USB_IP}"
echo "[rndis] WebUI via USB: http://${USB_IP}:8766  (no adb forward)"

if [ -f "${P4_ROOT}/systemd/r1-rndis-usb.service" ]; then
  install -m 644 "${P4_ROOT}/systemd/r1-rndis-usb.service" /etc/systemd/system/
  systemctl daemon-reload
  systemctl enable r1-rndis-usb.service
fi
