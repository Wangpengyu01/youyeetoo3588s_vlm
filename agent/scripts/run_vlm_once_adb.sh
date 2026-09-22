#!/bin/bash
# One-shot board VLM for adb (root shell). Avoids run_board_vlm + sudo/systemctl.
# Usage: adb shell "bash /userdata/agent/scripts/run_vlm_once_adb.sh [/path/to.jpg] [prompt]"
set -eu

IMAGE="${1:-/userdata/agent/run/camera_shot.jpg}"
PROMPT="${2:-用一句话描述画面}"
AGENT_ROOT="${AGENT_ROOT:-/userdata/agent}"

echo "[vlm-once] pause orchestrator + gst (proactive grab competes with RTSP)..."
bash "${AGENT_ROOT}/scripts/pause_rtsp_competitors.sh"

echo "[vlm-once] grab frame → ${IMAGE}"
bash "${AGENT_ROOT}/scripts/grab_camera_frame.sh" "${IMAGE}" || true
if [ ! -s "${IMAGE}" ]; then
  echo "[vlm-once] no image: ${IMAGE}" >&2
  exit 1
fi

bash "${AGENT_ROOT}/scripts/cooperative_stop_llm.sh"

echo "[vlm-once] infer (may take 1-3 min)..."
export P4_MAX_IDLE_MB=1500
CAP=$(bash /userdata/p4/scripts/vlm_see.sh "${IMAGE}" "${PROMPT}" 2>"${AGENT_ROOT}/logs/vlm_err.log" | tail -1)
echo "${CAP}"

bash "${AGENT_ROOT}/scripts/cooperative_start_llm.sh" || true
echo "[vlm-once] restart orchestrator (no systemctl via adb)..."
if ! pgrep -f 'orchestrator.main' >/dev/null 2>&1; then
  nohup python3 -m orchestrator.main --config "${AGENT_ROOT}/config/agent.yaml" \
    --agent-root "${AGENT_ROOT}" >>"${AGENT_ROOT}/logs/orchestrator.log" 2>&1 &
fi

echo "[vlm-once] done"
