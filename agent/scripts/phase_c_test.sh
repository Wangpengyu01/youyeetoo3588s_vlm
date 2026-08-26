#!/bin/bash
# Phase C acceptance: SenseVoice ASR partial/final + LLM
set -euo pipefail

AGENT_ROOT="${AGENT_ROOT:-/userdata/agent}"
TEST_WAV="${1:-/userdata/voice/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17/test_wavs/zh.wav}"

source /userdata/voice/scripts/voice_hw_board.sh 2>/dev/null || true
export PYTHONPATH="${AGENT_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"
export LD_LIBRARY_PATH="/userdata/voice/sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"

echo "=== Phase C 板端验收 ==="

echo "[1/3] SenseVoice offline smoke"
python3 - <<'PY'
import sys
sys.path.insert(0, "/userdata/agent")
from asr.sense_voice import SenseVoiceAsr
asr = SenseVoiceAsr()
text = asr.recognize_file("/userdata/voice/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17/test_wavs/zh.wav")
assert text, "empty ASR"
print("asr:", text)
PY

echo ""
echo "[2/3] inject-wav E2E (VAD -> ASR final -> LLM)"
pkill -f "orchestrator.main" 2>/dev/null || true
rm -f "${AGENT_ROOT}/run/last_utterance.wav"
timeout 120 python3 -m orchestrator.main \
  --config "${AGENT_ROOT}/config/agent.yaml" \
  --agent-root "${AGENT_ROOT}" \
  --inject-wav "${TEST_WAV}" \
  --no-partial \
  --log-level INFO 2>&1 | tee /tmp/phase_c_inject.log

grep -q "asr_final" /tmp/phase_c_inject.log || { echo "[fail] no asr_final in log"; exit 1; }
grep -q "\[llm\] reply" /tmp/phase_c_inject.log || { echo "[fail] no llm reply in log"; exit 1; }
echo "[ok] inject-wav pipeline passed"

echo ""
echo "[3/3] restart live orchestrator"
bash "${AGENT_ROOT}/scripts/start_orchestrator.sh"
echo "=== Phase C 完成 — speak to mic for live partial/final ==="
