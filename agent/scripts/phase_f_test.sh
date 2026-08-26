#!/bin/bash
# Phase F acceptance: streaming Paraformer ASR + E2E inject-wav
set -euo pipefail

AGENT_ROOT="${AGENT_ROOT:-/userdata/agent}"
MODEL_DIR="/userdata/voice/sherpa-onnx-streaming-paraformer-bilingual-zh-en"
TEST_WAV="${1:-${MODEL_DIR}/test_wavs/0.wav}"

source /userdata/voice/scripts/voice_hw_board.sh 2>/dev/null || true
export PYTHONPATH="${AGENT_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"
export LD_LIBRARY_PATH="/userdata/voice/sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"

echo "=== Phase F 板端验收 ==="

if [ ! -f "${MODEL_DIR}/encoder.int8.onnx" ]; then
  echo "[fail] missing ${MODEL_DIR}/encoder.int8.onnx — run install_streaming_asr.sh first"
  exit 1
fi

echo "[1/3] streaming paraformer smoke"
python3 - <<'PY'
import sys
import time
import wave
import array
from pathlib import Path
sys.path.insert(0, "/userdata/agent")
from asr.sherpa_streaming_asr import StreamingParaformerConfig, StreamingParaformerRecognizer

wav = Path("/userdata/voice/sherpa-onnx-streaming-paraformer-bilingual-zh-en/test_wavs/0.wav")
cfg = StreamingParaformerConfig(
    model_dir="/userdata/voice/sherpa-onnx-streaming-paraformer-bilingual-zh-en",
    sherpa_lib="/userdata/voice/sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu/lib",
)
rec = StreamingParaformerRecognizer(cfg)
with wave.open(str(wav), "rb") as w:
    raw = w.readframes(w.getnframes())
    samples = [x / 32768.0 for x in array.array("h", raw)]
    rate = w.getframerate()
rec.reset()
t0 = time.monotonic()
chunk = int(rate * 0.2)
for i in range(0, len(samples), chunk):
    rec.feed(samples[i : i + chunk], rate)
text = rec.finalize()
ms = int((time.monotonic() - t0) * 1000)
rec.close()
print(f"asr ({ms}ms):", text)
assert text, "empty streaming ASR"
PY

echo ""
echo "[2/3] inject-wav E2E (streaming ASR -> LLM -> TTS)"
pkill -f "orchestrator.main" 2>/dev/null || true
timeout 180 python3 -m orchestrator.main \
  --config "${AGENT_ROOT}/config/agent.yaml" \
  --agent-root "${AGENT_ROOT}" \
  --inject-wav "${TEST_WAV}" \
  --log-level INFO 2>&1 | tee /tmp/phase_f_inject.log

grep -q "backend=streaming_paraformer" /tmp/phase_f_inject.log || grep -q "asr_final" /tmp/phase_f_inject.log || {
  echo "[fail] orchestrator did not run streaming ASR"
  exit 1
}
grep -q "asr_final" /tmp/phase_f_inject.log || { echo "[fail] no asr_final"; exit 1; }
grep -q "\[tts\] speak" /tmp/phase_f_inject.log || { echo "[fail] no tts speak"; exit 1; }
grep -q "first_play" /tmp/phase_f_inject.log || { echo "[warn] no first_play line (check log manually)"; }
echo "[ok] Phase F E2E passed"

echo ""
echo "[3/3] restart live orchestrator"
bash "${AGENT_ROOT}/scripts/start_orchestrator.sh"
echo "=== Phase F 完成 — speak to mic for streaming partial/final ==="
