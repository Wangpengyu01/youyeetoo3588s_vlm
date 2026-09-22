#!/bin/bash
# Smoke: grab + VLM caption + LLM ping (legacy or P5b socket).
set -eu
AGENT="${AGENT_ROOT:-/userdata/agent}"
SOCK="/tmp/r1-llm.sock"
[[ -S /tmp/r1-vlm.sock ]] && SOCK="/tmp/r1-vlm.sock"

echo "=== [1] socket ping ($SOCK) ==="
python3 "${AGENT}/scripts/llm_client.py" --socket "${SOCK}" --ping || true

echo "=== [2] RTSP grab ==="
bash "${AGENT}/scripts/pause_rtsp_competitors.sh" || true
bash "${AGENT}/scripts/grab_camera_frame.sh" "${AGENT}/run/camera_shot.jpg"
ls -la "${AGENT}/run/camera_shot.jpg"

if [[ -S /tmp/r1-vlm.sock ]] && pgrep -f '/userdata/agent/bin/vlm_daemon' >/dev/null; then
  echo "=== [3] P5b see via socket ==="
  python3 "${AGENT}/scripts/vlm_client_see.py" "${AGENT}/run/camera_shot.jpg" "用一句话描述画面"
else
  echo "=== [3] skip legacy VLM (avoid 1828 fight with llm_daemon) ==="
  echo "start r1-vlm-daemon first, or run run_vlm_once_adb.sh manually"
fi

echo "=== [4] chat ==="
python3 "${AGENT}/scripts/llm_client.py" --socket "${SOCK}" --prompt "你好" --max-new 24 --no-stream

echo "=== smoke done ==="
