#!/bin/bash
# Record without beep — isolate mic hardware from playback/jack handler.
set -euo pipefail
source /userdata/voice/scripts/voice_env.sh
export MIC_ROUTE="${MIC_ROUTE:-main_board}"
export MIC_SOURCE="${MIC_SOURCE:-main}"
SEC="${1:-3}"
WAV="/tmp/mic_nobeep.wav"

echo "=== 无滴声录音 (${SEC}s) · ${MIC_ROUTE} ==="
bash /userdata/voice/scripts/mic_arm.sh
bash /userdata/voice/scripts/mic_record.sh "${WAV}" "${SEC}"
python3 /userdata/voice/scripts/analyze_wav.py "${WAV}"
