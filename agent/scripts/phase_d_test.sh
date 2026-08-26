#!/bin/bash
# Phase D acceptance: sentence TTS queue + E2E inject-wav
set -euo pipefail

AGENT_ROOT="${AGENT_ROOT:-/userdata/agent}"
TEST_WAV="${1:-/userdata/voice/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17/test_wavs/zh.wav}"

source /userdata/voice/scripts/voice_hw_board.sh 2>/dev/null || true
export PYTHONPATH="${AGENT_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"
export LD_LIBRARY_PATH="/userdata/voice/sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"

echo "=== Phase D 板端验收 ==="

echo "[1/3] TTS smoke"
python3 - <<'PY'
import sys
sys.path.insert(0, "/userdata/agent")
from tts.tts_engine import TtsEngine
TtsEngine().speak("语音合成测试。")
print("tts_ok")
PY

echo ""
echo "[2/3] inject-wav E2E (ASR -> LLM stream -> TTS)"
pkill -f "orchestrator.main" 2>/dev/null || true
timeout 180 python3 -m orchestrator.main \
  --config "${AGENT_ROOT}/config/agent.yaml" \
  --agent-root "${AGENT_ROOT}" \
  --inject-wav "${TEST_WAV}" \
  --no-partial \
  --log-level INFO 2>&1 | tee /tmp/phase_d_inject.log

grep -q "asr_final" /tmp/phase_d_inject.log || { echo "[fail] no asr_final"; exit 1; }
grep -q "\[tts\] speak" /tmp/phase_d_inject.log || { echo "[fail] no tts speak"; exit 1; }
grep -q "first_play" /tmp/phase_d_inject.log || { echo "[fail] no first_play latency"; exit 1; }
echo "[ok] E2E with TTS passed"

echo ""
echo "[3/3] restart live orchestrator"
bash "${AGENT_ROOT}/scripts/start_orchestrator.sh"
echo "=== Phase D 完成 — speak to mic for full voice chat ==="
