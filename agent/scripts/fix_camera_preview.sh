#!/bin/bash
# Fix grey/garbled WebUI preview: reset cache + restart frame daemon + orchestrator.
set -euo pipefail
AGENT="${AGENT_ROOT:-/userdata/agent}"

rm -f "${AGENT}/run/mediamtx_latest.jpg" "${AGENT}/run/latest_vlm.jpg" "${AGENT}/ui/latest_frame.jpg"
pkill -f mediamtx_rtsp_frame_daemon.sh 2>/dev/null || true
sleep 1
nohup bash "${AGENT}/scripts/mediamtx_rtsp_frame_daemon.sh" >>"${AGENT}/logs/mediamtx_frame_daemon.log" 2>&1 &
echo "[fix] waiting for valid 448 cache (max ~20s, prints every 2s)..."
for i in $(seq 1 10); do
  echo "[fix] poll ${i}/10..."
  if python3 - <<PY
import sys
sys.path.insert(0, "${AGENT}")
from pathlib import Path
from orchestrator.mediamtx_camera import _cache_file_valid
p = Path("${AGENT}/run/mediamtx_latest.jpg")
sys.exit(0 if _cache_file_valid(p) else 1)
PY
  then
    file "${AGENT}/run/mediamtx_latest.jpg"
    ls -la "${AGENT}/run/mediamtx_latest.jpg"
    cp -f "${AGENT}/run/mediamtx_latest.jpg" "${AGENT}/ui/latest_frame.jpg"
    chown youyeetoo:youyeetoo "${AGENT}/ui/latest_frame.jpg" 2>/dev/null || true
    break
  fi
  sleep 2
done
pkill -f gst-launch-1.0 2>/dev/null || true

pkill -f 'xiaolan_cli serve' 2>/dev/null || true
sleep 1
nohup python3 -m xiaolan_cli serve --config "${AGENT}/config/agent.yaml" --agent-root "${AGENT}" \
  >>"${AGENT}/logs/orchestrator.log" 2>&1 &
sleep 2
pgrep -af xiaolan_cli || true
echo "[fix] done — refresh WebUI (Ctrl+F5)"
