#!/bin/bash
# Run InternVL3.5-4B on latest RTSP frame (short caption)
set -euo pipefail
source "$(dirname "$0")/p4_env.sh"

SRC="${1:-${LATEST_FRAME}}"
if [ ! -s "${SRC}" ]; then
  echo "[VLM] 无输入帧: ${SRC}" >&2
  exit 1
fi

bash "${SCRIPTS}/wait_rknn.sh"
bash "${SCRIPTS}/p4_check_1828.sh"

python3 "${SCRIPTS}/frame_prepare.py" "${SRC}" "${VLM_FRAME}" "${VLM_SIZE}"

PROMPT="${2:-${VLM_PROMPT}}"
echo "[VLM] ${PROMPT}" >&2

export LD_LIBRARY_PATH="${VLM_LD_LIBRARY_PATH}"
cd "${VLM_DEMO}"

LOG=/tmp/vlm_see.log
T0=$(date +%s%3N)

if ! ./rknn_internvl3_demo \
  "${VLM_MODEL}/vision_InternVL3_5-4B.rknn" \
  "${VLM_MODEL}/vision_InternVL3_5-4B.weight" \
  "${VLM_MODEL}/llm_InternVL3_5-4B.rknn" \
  "${VLM_MODEL}/llm_InternVL3_5-4B.weight" \
  "${VLM_MODEL}/InternVL3_5-4B.tokenizer.gguf" \
  "${VLM_MODEL}/InternVL3_5-4B.embed.bin" \
  0xff 0xff "${VLM_FRAME}" "${PROMPT}" >"${LOG}" 2>&1; then
  tail -20 "${LOG}" >&2
  if grep -q "MODEL_SETUP fail" "${LOG}"; then
    echo "[VLM] 1828 MODEL_SETUP 失败 — 显存/会话被占用" >&2
    echo "[VLM] 若刚跑过 voice_chat：1828 已被 LLM-only 占用，与 VLM 互斥" >&2
    echo "[VLM] 若连续跑 p4_test：上一轮 VLM 可能未释放 EP 会话" >&2
    echo "[VLM] 解决: adb reboot 冷启动 → 只跑 P4（本轮勿跑 voice_chat）" >&2
  fi
  exit 1
fi

T1=$(date +%s%3N)
MS=$((T1 - T0))

TEXT=$(awk '
  /--> inference internvl3 llm model/ {show=1; next}
  show && /^--------------------Finished/ {exit}
  show && NF {print}
' "${LOG}" | sed '/^rknn_session_run$/d' | head -5)

VISION=$(grep -o 'Vision latency = [0-9.]* ms' "${LOG}" | tail -1 || true)

if [ -z "${TEXT}" ]; then
  TEXT=$(grep -E '^[^W ].*[一-龥a-zA-Z]' "${LOG}" | tail -3 || true)
fi

CAPTION="$(printf '%s\n' "${TEXT}" | sed '/^[[:space:]]*$/d' | head -1)"

echo "[VLM] ${MS} ms ${VISION}"
echo "${CAPTION}"

if [ -n "${CAPTION}" ]; then
  bash "${SCRIPTS}/p4_tts.sh" "${CAPTION}" || true
fi
