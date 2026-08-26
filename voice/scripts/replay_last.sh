#!/bin/bash
# Replay last ASR recording
set -euo pipefail
WAV="${1:-/tmp/last_asr.wav}"
if [ ! -f "${WAV}" ]; then
  echo "没有录音文件: ${WAV}" >&2
  exit 1
fi
python3 /userdata/voice/scripts/analyze_wav.py "${WAV}"
bash /userdata/voice/scripts/play_wav.sh "${WAV}" monitor
