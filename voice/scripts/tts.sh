#!/bin/bash
set -euo pipefail
source /userdata/voice/scripts/voice_env.sh

TEXT="${*:-}"
if [ -z "${TEXT}" ]; then
  echo "Usage: tts.sh \"要朗读的文字\"" >&2
  exit 1
fi

# Keep spoken replies short (long LLM answers are slow to synth and play)
MAX_CHARS="${TTS_MAX_CHARS:-120}"
if [ "${#TEXT}" -gt "${MAX_CHARS}" ]; then
  TEXT="${TEXT:0:MAX_CHARS}"
  echo "[TTS] 截断至 ${MAX_CHARS} 字" >&2
fi

OUT="/tmp/tts_out.wav"
echo "[TTS] ${TEXT}" >&2

echo "[TTS] 合成中..." >&2
MATCHA_DIR="${VOICE_ROOT}/matcha-icefall-zh-baker"
VOCODER="${VOICE_ROOT}/vocos-22khz-univ.onnx"

if [ -f "${MATCHA_DIR}/model-steps-3.onnx" ] && [ -f "${VOCODER}" ]; then
  if ! "${SHERPA_BIN}/sherpa-onnx-offline-tts" \
    --matcha-acoustic-model="${MATCHA_DIR}/model-steps-3.onnx" \
    --matcha-vocoder="${VOCODER}" \
    --matcha-lexicon="${MATCHA_DIR}/lexicon.txt" \
    --matcha-tokens="${MATCHA_DIR}/tokens.txt" \
    --matcha-dict-dir="${MATCHA_DIR}/dict" \
    --num-threads=2 \
    --output-filename="${OUT}" \
    "${TEXT}" >/dev/null 2>&1; then
    echo "[TTS] 合成失败" >&2
    exit 1
  fi
elif [ -d "${TTS_MODEL}" ] && [ -f "${TTS_MODEL}/model.onnx" ]; then
  if ! "${SHERPA_BIN}/sherpa-onnx-offline-tts" \
    --vits-model="${TTS_MODEL}/model.onnx" \
    --vits-tokens="${TTS_MODEL}/tokens.txt" \
    --vits-lexicon="${TTS_MODEL}/lexicon.txt" \
    --vits-dict-dir="${TTS_MODEL}/dict" \
    --sid=0 \
    --num-threads=2 \
    --output-filename="${OUT}" \
    "${TEXT}" >/dev/null 2>&1; then
    echo "[TTS] 合成失败" >&2
    exit 1
  fi
else
  echo "[TTS] 未找到有效的 TTS 模型" >&2
  exit 1
fi

if [ ! -s "${OUT}" ]; then
  echo "[TTS] 输出文件为空: ${OUT}" >&2
  exit 1
fi

echo "[TTS] 播放中（播完前请勿 Ctrl+C）..." >&2
bash /userdata/voice/scripts/play_wav.sh "${OUT}"
echo "[TTS] 播放完成" >&2
