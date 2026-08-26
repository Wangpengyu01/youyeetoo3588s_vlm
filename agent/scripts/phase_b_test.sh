#!/bin/bash
# Phase B acceptance: VAD + orchestrator skeleton
set -euo pipefail

AGENT_ROOT="${AGENT_ROOT:-/userdata/agent}"
LOG="${AGENT_ROOT}/logs/orchestrator.log"
UTT="${AGENT_ROOT}/run/last_utterance.wav"
TEST_WAV="${1:-/tmp/last_asr.wav}"
FALLBACK_WAV="/userdata/voice/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17/test_wavs/zh.wav"
if [[ ! -f "${TEST_WAV}" && -f "${FALLBACK_WAV}" ]]; then
  TEST_WAV="${FALLBACK_WAV}"
fi

source /userdata/voice/scripts/voice_hw_board.sh 2>/dev/null || true
export PYTHONPATH="${AGENT_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"
export LD_LIBRARY_PATH="/userdata/voice/sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"

echo "=== Phase B 板端验收 ==="

echo "[1/4] sherpa Silero VAD ctypes smoke"
python3 - <<'PY'
import sys
sys.path.insert(0, "/userdata/agent")
from asr.sherpa_vad import SherpaVad
with SherpaVad(
    "/userdata/voice/silero_vad.onnx",
    "/userdata/voice/sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu/lib",
) as vad:
    vad.accept_pcm_float32([0.0] * 512)
    print("vad_ok")
PY

echo ""
echo "[2/4] llm_daemon ping"
if [[ -S /tmp/r1-llm.sock ]]; then
  python3 "${AGENT_ROOT}/scripts/llm_client.py" --ping
else
  echo "WARN: llm_daemon socket missing — start with start_llm_daemon.sh"
fi

echo ""
echo "[3/4] offline inject-wav (VAD -> ASR stub)"
rm -f "${UTT}"
if [[ -f "${TEST_WAV}" ]]; then
  timeout 30 python3 -m orchestrator.main \
    --config "${AGENT_ROOT}/config/agent.yaml" \
    --agent-root "${AGENT_ROOT}" \
    --inject-wav "${TEST_WAV}" \
    --log-level INFO &
  INJ_PID=$!
  wait "${INJ_PID}" || true
  if [[ -f "${UTT}" ]]; then
    echo "[ok] utterance saved: ${UTT} ($(wc -c <"${UTT}") bytes)"
  else
    echo "[fail] no utterance at ${UTT}"
    exit 1
  fi
else
  echo "SKIP inject-wav — ${TEST_WAV} not found (run voice ASR once or pass wav path)"
fi

echo ""
echo "[4/4] live orchestrator (5s sample — speak now if mic connected)"
pkill -f "orchestrator.main" 2>/dev/null || true
rm -f "${AGENT_ROOT}/run/orchestrator.pid"
bash "${AGENT_ROOT}/scripts/start_orchestrator.sh"
sleep 2
if [[ -f "${AGENT_ROOT}/run/orchestrator.pid" ]] && kill -0 "$(cat "${AGENT_ROOT}/run/orchestrator.pid")" 2>/dev/null; then
  echo "[ok] orchestrator running pid=$(cat "${AGENT_ROOT}/run/orchestrator.pid")"
  echo "     tail -f ${LOG}"
  echo "     speak 2+ seconds toward onboard mic to see ASR state"
else
  echo "[fail] orchestrator not running — check ${LOG}"
  tail -20 "${LOG}" 2>/dev/null || true
  exit 1
fi

echo "=== Phase B 完成 ==="
