#!/bin/bash
# Spike S0: LLM baseline + optional VLM (script path). Safe on RK3588 (no blocking systemctl).
# Run: bash /userdata/agent/scripts/vlm_spike_s0_board.sh
# Skip VLM (LLM-only): SKIP_VLM=1 bash ...
set -eu

AGENT_ROOT="${AGENT_ROOT:-/userdata/agent}"
LOG_DIR="${AGENT_ROOT}/logs/vlm_spike"
mkdir -p "${LOG_DIR}"
STAMP=$(date +%Y%m%d_%H%M%S)
LOG="${LOG_DIR}/s0_${STAMP}.log"

{
  echo "=== VLM Spike S0 @ $(date -Iseconds) ==="

  if systemctl is-active --quiet r1-llm-daemon 2>/dev/null; then
    echo "[S0a] r1-llm-daemon active"
  else
    echo "[S0a] starting r1-llm-daemon..."
    timeout 8 sudo systemctl start r1-llm-daemon 2>/dev/null || true
    sleep 3
  fi

  T0=$(date +%s%3N)
  if python3 "${AGENT_ROOT}/scripts/llm_client.py" --ping 2>/dev/null; then
    echo "[S0a] llm ping OK"
  else
    echo "[S0a] llm ping FAIL"
  fi
  T1=$(date +%s%3N)
  echo "[S0a] ping_wall_ms=$((T1 - T0))"

  T0=$(date +%s%3N)
  if python3 "${AGENT_ROOT}/scripts/llm_client.py" --prompt "你好" --max-new 24 --no-stream >/tmp/s0_chat.txt 2>/tmp/s0_chat.err; then
    OUT="chat_ok $(head -c 40 /tmp/s0_chat.txt 2>/dev/null)"
  else
    OUT="chat_fail $(head -1 /tmp/s0_chat.err 2>/dev/null)"
  fi
  T1=$(date +%s%3N)
  echo "[S0a] chat_wall_ms=$((T1 - T0)) result=${OUT}"

  FRAME="/userdata/agent/run/camera_shot.jpg"
  if bash /userdata/agent/scripts/grab_camera_frame.sh "${FRAME}"; then
    echo "[S0b] grab OK size=$(stat -c%s "${FRAME}")"
  else
    echo "[S0b] grab FAIL"
  fi

  if [ "${SKIP_VLM:-0}" = "1" ]; then
    echo "[S0c] SKIP_VLM=1 — skip board VLM (use after reboot if systemctl D-state)"
  elif [ -f "/userdata/p4/scripts/vlm_see.sh" ]; then
    echo "[S0c] run_board_vlm with 180s cap..."
    T0=$(date +%s%3N)
    CAP=$(timeout 180 bash "${AGENT_ROOT}/scripts/run_board_vlm.sh" "${FRAME}" "用一句话描述画面" 2>/dev/null || echo "vlm_timeout_or_fail")
    T1=$(date +%s%3N)
    echo "[S0c] vlm_wall_ms=$((T1 - T0))"
    echo "[S0c] caption=${CAP:0:160}"
  fi

  sleep 2
  for i in $(seq 1 45); do
    if python3 "${AGENT_ROOT}/scripts/llm_client.py" --ping 2>/dev/null; then
      echo "[S0d] llm recovered after ${i}s"
      break
    fi
    sleep 1
  done

  echo "=== S0 done ==="
} 2>&1 | tee -a "${LOG}"

echo "log: ${LOG}"
