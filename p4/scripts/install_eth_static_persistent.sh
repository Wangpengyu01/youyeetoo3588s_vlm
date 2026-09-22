#!/bin/bash
# One-time: persist eth0 static IP for P4/RTSP camera (survives reboot).
# Run on board: sudo bash /userdata/p4/scripts/install_eth_static_persistent.sh
set -euo pipefail
source "$(dirname "$0")/p4_env.sh"

NAME="${P4_NM_CONN:-p4-camera-eth}"
IF="${P4_ETH_IF:-eth0}"
CIDR="${STATIC_IP}/${STATIC_PREFIX}"
CAM_IP=$(echo "${RTSP_URL}" | sed -E 's|^rtsp://([^@/]+@)?([^:/]+).*|\2|')

if [ ! -d "/sys/class/net/${IF}" ]; then
  echo "[NET-INSTALL] 未找到网卡 ${IF}" >&2
  exit 1
fi

echo "[NET-INSTALL] ${IF} → ${CIDR} gw=${STATIC_GW} (NM: ${NAME})"

if nmcli -t -f NAME con show 2>/dev/null | grep -Fxq "${NAME}"; then
  nmcli con mod "${NAME}" \
    connection.interface-name "${IF}" \
    connection.autoconnect yes \
    ipv4.method manual \
    ipv4.addresses "${CIDR}" \
    ipv4.gateway "${STATIC_GW}" \
    ipv4.dns "${STATIC_DNS}" \
    ipv4.ignore-auto-dns yes \
    ipv6.method disabled
else
  nmcli con add type ethernet ifname "${IF}" con-name "${NAME}" autoconnect yes \
    ipv4.method manual \
    ipv4.addresses "${CIDR}" \
    ipv4.gateway "${STATIC_GW}" \
    ipv4.dns "${STATIC_DNS}" \
    ipv4.ignore-auto-dns yes \
    ipv6.method disabled
fi

nmcli con down "${NAME}" 2>/dev/null || true
sleep 1
nmcli con up "${NAME}"

echo "[NET-INSTALL] 当前:"
nmcli -f GENERAL.STATE,IP4.ADDRESS dev show "${IF}" 2>/dev/null || true

if [ -n "${CAM_IP}" ]; then
  echo "[NET-INSTALL] ping ${CAM_IP} ..."
  ping -c 2 -W 2 "${CAM_IP}"
fi

echo "[NET-INSTALL] OK — enable: sudo systemctl enable r1-p4-eth.service"
