#!/bin/bash
# Boot: bring up NM profile p4-camera-eth (no ip flush / no orchestrator hooks).
set -eu
source "$(dirname "$0")/p4_env.sh"

NAME="${P4_NM_CONN:-p4-camera-eth}"
IF="${P4_ETH_IF:-eth0}"
CIDR="${STATIC_IP}/${STATIC_PREFIX}"
CAM_IP=$(echo "${RTSP_URL}" | sed -E 's|^rtsp://([^@/]+@)?([^:/]+).*|\2|')

cam_ok() {
  [ -n "${CAM_IP}" ] && timeout 2 bash -c "echo > /dev/tcp/${CAM_IP}/554" 2>/dev/null
}

if cam_ok; then
  echo "[NET-BOOT] camera ${CAM_IP}:554 OK — skip"
  exit 0
fi

if command -v nmcli >/dev/null 2>&1 && nmcli -t -f NAME con show 2>/dev/null | grep -Fxq "${NAME}"; then
  echo "[NET-BOOT] nmcli con up ${NAME}"
  timeout 8 nmcli con up "${NAME}" 2>/dev/null || true
  sleep 2
  if cam_ok; then
    echo "[NET-BOOT] OK after NM"
    exit 0
  fi
fi

# Lightweight fallback when NM is slow/unavailable (common from adb); needs cap_net_admin (root adb OK).
if [ -d "/sys/class/net/${IF}" ] && [ "$(id -u)" -eq 0 ]; then
  if ! ip -4 -br addr show dev "${IF}" 2>/dev/null | grep -q '192\.168\.2\.'; then
    echo "[NET-BOOT] ip fallback ${IF} ${CIDR} (camera segment)"
    ip link set "${IF}" up 2>/dev/null || true
    ip addr add "${CIDR}" dev "${IF}" 2>/dev/null || true
    if [ -n "${CAM_IP}" ]; then
      ip route add "${CAM_IP}/32" dev "${IF}" 2>/dev/null || true
    fi
    sleep 1
    if cam_ok; then
      echo "[NET-BOOT] OK after ip fallback"
      exit 0
    fi
  fi
fi

echo "[NET-BOOT] WARN: camera unreachable — run: bash /userdata/p4/scripts/install_eth_static_persistent.sh" >&2
exit 0
