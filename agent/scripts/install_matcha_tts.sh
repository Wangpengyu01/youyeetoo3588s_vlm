#!/bin/bash
# Download matcha-icefall-zh-baker + vocos vocoder for R1 agent TTS
set -euo pipefail

VOICE_ROOT="${VOICE_ROOT:-/userdata/voice}"
MATCHA_DIR="${VOICE_ROOT}/matcha-icefall-zh-baker"
VOCODER="${VOICE_ROOT}/vocos-22khz-univ.onnx"
SHERPA_TTS="${VOICE_ROOT}/sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu/bin/sherpa-onnx-offline-tts"
SHERPA_LIB="${VOICE_ROOT}/sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu/lib"

export LD_LIBRARY_PATH="${SHERPA_LIB}${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"

echo "=== Install Matcha TTS (zh-baker) ==="

if [ ! -f "${MATCHA_DIR}/model-steps-3.onnx" ]; then
  echo "[1/3] download matcha-icefall-zh-baker (PC: adb push /tmp/matcha-icefall-zh-baker.tar.bz2 then tar xf)"
  tmp="/tmp/matcha-icefall-zh-baker.tar.bz2"
  wget -O "${tmp}" \
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/matcha-icefall-zh-baker.tar.bz2"
  tar xf "${tmp}" -C "${VOICE_ROOT}"
  rm -f "${tmp}"
else
  echo "[1/3] matcha model already present"
fi

if [ ! -f "${VOCODER}" ]; then
  echo "[2/3] download vocos-22khz-univ.onnx"
  wget -O "${VOCODER}" \
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/vocoder-models/vocos-22khz-univ.onnx"
else
  echo "[2/3] vocoder already present"
fi

echo "[3/3] smoke test"
"${SHERPA_TTS}" \
  --matcha-acoustic-model="${MATCHA_DIR}/model-steps-3.onnx" \
  --matcha-vocoder="${VOCODER}" \
  --matcha-lexicon="${MATCHA_DIR}/lexicon.txt" \
  --matcha-tokens="${MATCHA_DIR}/tokens.txt" \
  --matcha-dict-dir="${MATCHA_DIR}/dict" \
  --num-threads=2 \
  --output-filename=/tmp/matcha_smoke.wav \
  "你好，这是新的语音合成测试。"

source /userdata/voice/scripts/voice_hw_board.sh 2>/dev/null || true
bash /userdata/voice/scripts/play_wav.sh /tmp/matcha_smoke.wav
echo "=== Matcha TTS ready ==="
