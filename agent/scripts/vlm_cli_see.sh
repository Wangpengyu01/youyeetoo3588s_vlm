#!/bin/bash
# Grab latest RTSP frame + InternVL caption. Caller must release RK1828 (coop stop or vlm_daemon teardown).
# Usage: bash vlm_cli_see.sh ["prompt"]
set -eu

AGENT_ROOT="${AGENT_ROOT:-/userdata/agent}"
P4="${P4_ROOT:-/userdata/p4}"
FRAME="${AGENT_ROOT}/run/camera_shot.jpg"
PROMPT="${1:-${VLM_SEE_PROMPT:-用一句话描述当前画面。}}"

bash "${AGENT_ROOT}/scripts/pause_rtsp_competitors.sh" 2>/dev/null || true
bash "${AGENT_ROOT}/scripts/grab_camera_frame.sh" "${FRAME}"

bash "${P4}/scripts/vlm_see.sh" "${FRAME}" "${PROMPT}" | tail -1
