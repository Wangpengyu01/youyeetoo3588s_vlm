#!/bin/bash
set -euo pipefail
source /userdata/voice/scripts/voice_env.sh

SEC="${1:-5}"
WAV="/tmp/mic_diag.wav"

bash /userdata/voice/scripts/mic_setup.sh

echo
echo "[DIAG] 滴——请立即对着麦克风说话 (${SEC}s)..."
bash /userdata/voice/scripts/beep.sh 2>/dev/null || true
bash /userdata/voice/scripts/mic_arm.sh
bash /userdata/voice/scripts/mic_record.sh "${WAV}" "${SEC}"

python3 /userdata/voice/scripts/analyze_wav.py "${WAV}"

echo
echo "[DIAG] ▶ 回放录音 (monitor)..."
bash /userdata/voice/scripts/play_wav.sh "${WAV}" monitor

echo
echo "[DIAG] ASR 原始输出:"
RAW=$("${SHERPA_BIN}/sherpa-onnx-offline" \
  --tokens="${ASR_MODEL}/tokens.txt" \
  --sense-voice-model="${ASR_MODEL}/model.int8.onnx" \
  --sense-voice-language=zh \
  --num-threads=2 \
  "${WAV}" 2>&1 | grep '"text"' | tail -1 || true)
echo "  ${RAW:-<empty>}"

TEXT=$(echo "${RAW}" | python3 /userdata/voice/scripts/asr_parse.py 2>/dev/null || true)
echo "[DIAG] 识别文字: ${TEXT:-<空>}"
