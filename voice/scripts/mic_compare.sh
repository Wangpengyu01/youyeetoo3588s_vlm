#!/bin/bash
# Compare mic routes while you speak (uses mic_record keeper).
set -euo pipefail
source /userdata/voice/scripts/voice_env.sh
SEC="${1:-3}"

ROUTES="${MIC_PROBE_ROUTES:-headset_line2 headset_miclr headset_line1 main_board}"

for route in ${ROUTES}; do
  echo "========== ${route} =========="
  export MIC_ROUTE="${route}"
  if [[ "${route}" == main_* ]]; then
    export MIC_SOURCE=main
  else
    export MIC_SOURCE=headset
  fi
  bash /userdata/voice/scripts/mic_setup.sh
  WAV="/tmp/mic_cmp_${route}.wav"
  bash /userdata/voice/scripts/mic_record.sh "${WAV}" "${SEC}"
  python3 /userdata/voice/scripts/analyze_wav.py "${WAV}"
  echo -n "ASR: "
  /userdata/voice/sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu/bin/sherpa-onnx-offline \
    --tokens="${ASR_MODEL}/tokens.txt" \
    --sense-voice-model="${ASR_MODEL}/model.int8.onnx" \
    --sense-voice-language=zh \
    --num-threads=2 \
    "${WAV}" 2>/dev/null | python3 /userdata/voice/scripts/asr_parse.py || echo "<空>"
  echo
done
