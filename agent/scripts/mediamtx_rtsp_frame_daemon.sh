#!/bin/bash
# Keep mediamtx_latest.jpg fresh via local RTSP (warm relay, ~sub-second updates).
set -euo pipefail
AGENT="${AGENT_ROOT:-/userdata/agent}"
OUT="${AGENT}/run/mediamtx_latest.jpg"
RTSP="${MEDIAMTX_RTSP:-rtsp://127.0.0.1:8554/cam}"
export RTSP_URL="${RTSP}"
INTERVAL="${MEDIAMTX_FRAME_INTERVAL:-0.25}"
SIZE="${VLM_SIZE:-448}"
export PYTHONPATH="${AGENT}"
export GRAB_TIMEOUT_SEC=15

mkdir -p "${AGENT}/run" "${AGENT}/logs"
echo "[frame-daemon] rtsp=${RTSP} interval=${INTERVAL}s out=${OUT}"
# Drop corrupt huge cache from legacy p4 direct-grab mistakes
if [[ -f "${OUT}" ]] && [[ "$(stat -c%s "${OUT}" 2>/dev/null || echo 0)" -gt 900000 ]]; then
  rm -f "${OUT}"
  echo "[frame-daemon] removed oversized stale ${OUT}"
fi

while true; do
  TMP="${OUT}.part"
  rm -f "${TMP}"
  if python3 - <<PY 2>/dev/null; then
import os, sys
from pathlib import Path
sys.path.insert(0, "${AGENT}")
from orchestrator.rtsp_frame import grab_rtsp_frame
from orchestrator.mediamtx_camera import _cache_file_valid
tmp = Path("${TMP}")
ok = grab_rtsp_frame("${RTSP}", tmp, timeout=float(os.environ.get("GRAB_TIMEOUT_SEC", "15")), transport="tcp", size=int("${SIZE}"))
sys.exit(0 if ok and _cache_file_valid(tmp) else 1)
PY
    mv -f "${TMP}" "${OUT}"
    UI="${AGENT}/ui/latest_frame.jpg"
    cp -f "${OUT}" "${UI}.part" && mv -f "${UI}.part" "${UI}"
    chown youyeetoo:youyeetoo "${UI}" 2>/dev/null || true
  else
    rm -f "${TMP}"
  fi
  sleep "${INTERVAL}"
done
