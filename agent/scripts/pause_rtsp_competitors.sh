#!/bin/bash
# Free RTSP/netlink before manual grab or vlm-once (orchestrator proactive loop uses gst-launch).
# Usage: bash /userdata/agent/scripts/pause_rtsp_competitors.sh
set -eu

STOP_ORCH="${STOP_ORCH:-1}"

pkill -9 -f 'gst-launch-1.0' 2>/dev/null || true
if [ "${STOP_ORCH}" = "1" ]; then
  pkill -TERM -f 'orchestrator.main' 2>/dev/null || true
  sleep 0.5
  pkill -9 -f 'orchestrator.main' 2>/dev/null || true
fi
sleep 0.5
echo "[pause-rtsp] gst/orchestrator cleared (STOP_ORCH=${STOP_ORCH})"
