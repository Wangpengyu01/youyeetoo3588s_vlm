#!/bin/bash
# Apply static IPv4 on eth0 via NetworkManager (Ubuntu 22.04 R1)
set -euo pipefail
source "$(dirname "$0")/p4_env.sh"

CIDR="${STATIC_IP}/${STATIC_PREFIX}"

echo "[NET] 设置 ${NM_CONN} → ${CIDR} gw=${STATIC_GW}"

nmcli con mod "${NM_CONN}" \
  ipv4.method manual \
  ipv4.addresses "${CIDR}" \
  ipv4.gateway "${STATIC_GW}" \
  ipv4.dns "${STATIC_DNS}" \
  ipv4.ignore-auto-dns yes \
  ipv6.method ignore

nmcli con down "${NM_CONN}" 2>/dev/null || true
sleep 1
nmcli con up "${NM_CONN}"

echo "[NET] 当前地址:"
ip -br addr show eth0
echo "[NET] 路由:"
ip route | grep -E 'default|192.168.2' || true

CAM_IP=$(echo "${RTSP_URL}" | sed -E 's|rtsp://([^:/]+).*|\1|')
echo "[NET] ping 摄像机 ${CAM_IP} ..."
ping -c 2 -W 2 "${CAM_IP}" || {
  echo "[NET] 警告: 摄像机 ping 不通，请确认网线/网段/网关" >&2
  exit 1
}

echo "[NET] OK"
