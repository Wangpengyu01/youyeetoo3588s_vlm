#!/bin/bash
# Download streaming paraformer int8 files (no full 1GB tar needed)
set -euo pipefail

VOICE_ROOT="${VOICE_ROOT:-/userdata/voice}"
MODEL_DIR="${VOICE_ROOT}/sherpa-onnx-streaming-paraformer-bilingual-zh-en"
HF="https://hf-mirror.com/csukuangfj/sherpa-onnx-streaming-paraformer-bilingual-zh-en/resolve/main"
GITHUB="https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-streaming-paraformer-bilingual-zh-en.tar.bz2"
URL_MIRROR="https://huggingface.co/xumo/onnx_models/resolve/main/sherpa-onnx-streaming-paraformer-bilingual-zh-en.tar.bz2"

export LD_LIBRARY_PATH="${VOICE_ROOT}/sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"

mkdir -p "${MODEL_DIR}/test_wavs"

fetch() {
  local name="$1"
  local url="$2"
  if [ -f "${MODEL_DIR}/${name}" ]; then
    echo "  present: ${name}"
    return 0
  fi
  echo "  download: ${name}"
  wget -O "${MODEL_DIR}/${name}" "${url}"
}

echo "=== Install Streaming Paraformer ASR (int8 files) ==="

if [ ! -f "${MODEL_DIR}/encoder.int8.onnx" ]; then
  echo "[1/2] fetch encoder/decoder/tokens from HF mirror"
  fetch "encoder.int8.onnx" "${HF}/encoder.int8.onnx" || fetch "encoder.int8.onnx" "https://huggingface.co/csukuangfj/sherpa-onnx-streaming-paraformer-bilingual-zh-en/resolve/main/encoder.int8.onnx"
  fetch "decoder.int8.onnx" "${HF}/decoder.int8.onnx" || fetch "decoder.int8.onnx" "https://huggingface.co/csukuangfj/sherpa-onnx-streaming-paraformer-bilingual-zh-en/resolve/main/decoder.int8.onnx"
  fetch "tokens.txt" "${HF}/tokens.txt"
  fetch "test_wavs/0.wav" "${HF}/test_wavs/0.wav"
else
  echo "[1/2] int8 model already present"
fi

echo "[2/2] smoke test"
export PYTHONPATH="/userdata/agent${PYTHONPATH:+:${PYTHONPATH}}"
python3 - <<'PY'
import sys
sys.path.insert(0, "/userdata/agent")
from asr.sherpa_streaming_asr import StreamingParaformerConfig, StreamingParaformerRecognizer
import wave, array
from pathlib import Path

cfg = StreamingParaformerConfig(
    model_dir="/userdata/voice/sherpa-onnx-streaming-paraformer-bilingual-zh-en",
    sherpa_lib="/userdata/voice/sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu/lib",
)
rec = StreamingParaformerRecognizer(cfg)
wav = Path("/userdata/voice/sherpa-onnx-streaming-paraformer-bilingual-zh-en/test_wavs/0.wav")
with wave.open(str(wav), "rb") as w:
    raw = w.readframes(w.getnframes())
    samples = [x / 32768.0 for x in array.array("h", raw)]
    rate = w.getframerate()
rec.reset()
chunk = int(rate * 0.2)
for i in range(0, len(samples), chunk):
    rec.feed(samples[i : i + chunk], rate)
text = rec.finalize()
rec.close()
print("asr:", text)
assert text, "empty ASR"
PY

echo "=== Streaming Paraformer ASR ready ==="
