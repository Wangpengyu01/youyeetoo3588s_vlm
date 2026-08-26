#!/bin/bash
# ASR → TTS echo test (no LLM). SH1.25 L/R + board mic.
set -euo pipefail
source /userdata/voice/scripts/voice_hw_board.sh

TEXT="$(bash /userdata/voice/scripts/asr.sh)" || {
  echo "[asr_tts] ASR 失败，未进入 TTS" >&2
  exit 1
}
bash /userdata/voice/scripts/tts.sh "${TEXT}"
