#!/bin/bash
# Reliable RTSP single frame for VLM tests (writable paths, longer timeout, fallbacks).
# Usage: bash /userdata/agent/scripts/grab_camera_frame.sh [out.jpg]
set -eu

AGENT_ROOT="${AGENT_ROOT:-/userdata/agent}"
OUT="${1:-${AGENT_ROOT}/run/camera_shot.jpg}"
P4="${P4_ROOT:-/userdata/p4}"

mkdir -p "$(dirname "${OUT}")" "${AGENT_ROOT}/logs" "${AGENT_ROOT}/run" 2>/dev/null || true

cam_tcp_ok() {
  local url="${RTSP_URL:-}"
  if [ -z "${url}" ] && [ -f "${P4}/config/rtsp.env" ]; then
    # shellcheck disable=SC1090
    set -a
    source "${P4}/config/rtsp.env"
    set +a
  fi
  local cam_ip
  cam_ip=$(echo "${RTSP_URL:-}" | sed -E 's|^rtsp://([^@/]+@)?([^:/]+).*|\2|')
  [ -n "${cam_ip}" ] && timeout 2 bash -c "echo > /dev/tcp/${cam_ip}/554" 2>/dev/null
}

# Network for camera segment
if [ -f "${P4}/scripts/boot_eth_static.sh" ]; then
  bash "${P4}/scripts/boot_eth_static.sh" || true
fi

export RTSP_GRAB_LOG="${AGENT_ROOT}/logs/rtsp_grab.log"
export GRAB_TIMEOUT_SEC="${GRAB_TIMEOUT_SEC:-18}"
export GRAB_WAIT_LOOPS="${GRAB_WAIT_LOOPS:-80}"
: >"${RTSP_GRAB_LOG}" 2>/dev/null || RTSP_GRAB_LOG="/dev/null"

echo "[grab] target=${OUT} timeout=${GRAB_TIMEOUT_SEC}s log=${RTSP_GRAB_LOG}"

try_p4_grab() {
  bash "${P4}/scripts/rtsp_grab_once.sh" "${OUT}"
}

ATTEMPTS="${GRAB_ATTEMPTS:-2}"
a=1
while [ "${a}" -le "${ATTEMPTS}" ]; do
  if ! cam_tcp_ok; then
    echo "[grab] camera :554 not reachable (attempt ${a}/${ATTEMPTS}) — boot eth..." >&2
    bash "${P4}/scripts/boot_eth_static.sh" 2>/dev/null || true
    sleep 2
  fi
  if try_p4_grab; then
    echo "[grab] ok p4 $(wc -c < "${OUT}") bytes (attempt ${a})"
    exit 0
  fi
  a=$((a + 1))
  [ "${a}" -le "${ATTEMPTS}" ] && sleep 2
done

# Python helper (DEVNULL gst + p4 retry)
if [ -f "${AGENT_ROOT}/orchestrator/rtsp_frame.py" ]; then
  RTSP_URL="${RTSP_URL:-}"
  if [ -z "${RTSP_URL}" ] && [ -f "${P4}/config/rtsp.env" ]; then
    # shellcheck disable=SC1090
    set -a
    source "${P4}/config/rtsp.env"
    set +a
  fi
  if [ -n "${RTSP_URL:-}" ]; then
    echo "[grab] fallback rtsp_frame.py..."
    if python3 - <<PY
import os, sys
sys.path.insert(0, "${AGENT_ROOT}")
from pathlib import Path
from orchestrator.rtsp_frame import grab_rtsp_frame
url = os.environ.get("RTSP_URL", "")
out = Path("${OUT}")
ok = grab_rtsp_frame(url, out, timeout=float(os.environ.get("GRAB_TIMEOUT_SEC", "18")))
sys.exit(0 if ok else 1)
PY
    then
      echo "[grab] ok python $(wc -c < "${OUT}") bytes"
      exit 0
    fi
  fi
fi

echo "[grab] FAIL — see ${RTSP_GRAB_LOG}; check eth0, rtsp.env, ping camera" >&2
exit 1
