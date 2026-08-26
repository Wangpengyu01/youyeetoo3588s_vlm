#!/bin/bash
set -euo pipefail
source /userdata/voice/scripts/voice_hw_board.sh

SCRIPTS=/userdata/voice/scripts

echo "=== R1 语音对话 (3588 ASR/TTS + 1828 LLM) ==="
echo "回车开始录音，Ctrl+C 退出"
echo

while true; do
  read -r -p "按回车开始说话... " _

  TEXT=$(bash "${SCRIPTS}/asr.sh") || {
    echo "[提示] 可单独回放: bash ${SCRIPTS}/replay_last.sh"
    continue
  }

  echo "[LLM] 思考中..."
  REPLY=$(python3 "${SCRIPTS}/llm_ask.py" "${TEXT}" 2>/dev/null)
  if [ -z "${REPLY}" ]; then
    echo "[LLM] 无回复"
    continue
  fi
  echo "[LLM] ${REPLY}"

  bash "${SCRIPTS}/tts.sh" "${REPLY}" || echo "[TTS] 播放失败，可重试: bash ${SCRIPTS}/tts.sh \"${REPLY:0:80}\"" >&2
  echo
done
