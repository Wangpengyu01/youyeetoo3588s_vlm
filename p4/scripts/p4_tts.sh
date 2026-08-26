#!/bin/bash
# Speak VLM caption on J368 stereo (3588 sherpa TTS). Fails open if no voice stack.
set -eu

TEXT="${1:-}"
P4_TTS="${P4_TTS:-1}"
VOICE_SCRIPTS="${VOICE_SCRIPTS:-/userdata/voice/scripts}"

if [ "${P4_TTS}" = "0" ] || [ -z "${TEXT}" ]; then
  exit 0
fi

TTS_SH="${VOICE_SCRIPTS}/tts.sh"
HW_SH="${VOICE_SCRIPTS}/voice_hw_board.sh"

if [ ! -f "${TTS_SH}" ]; then
  echo "[P4-TTS] 跳过：未安装 voice 栈 (${TTS_SH})" >&2
  exit 0
fi

TEXT="$(printf '%s\n' "${TEXT}" | sed '/^[[:space:]]*$/d' | head -1)"
if [ -z "${TEXT}" ]; then
  exit 0
fi

if [ -f "${HW_SH}" ]; then
  # shellcheck disable=SC1090
  source "${HW_SH}" >/dev/null
fi

echo "[P4-TTS] 播报: ${TEXT}" >&2
if ! bash "${TTS_SH}" "${TEXT}"; then
  echo "[P4-TTS] 播报失败（检查 J368 喇叭 / voice 模型）" >&2
fi
