#!/bin/bash
# Phase E acceptance: WebSocket agent_api event stream
set -euo pipefail

AGENT_ROOT="${AGENT_ROOT:-/userdata/agent}"
TEST_WAV="${1:-/userdata/voice/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17/test_wavs/zh.wav}"

source /userdata/voice/scripts/voice_hw_board.sh 2>/dev/null || true
export PYTHONPATH="${AGENT_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"
export LD_LIBRARY_PATH="/userdata/voice/sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"

echo "=== Phase E 板端验收 ==="

echo "[1/3] start orchestrator (background inject E2E, no TTS)"
pkill -f "orchestrator.main" 2>/dev/null || true
rm -f /tmp/phase_e_orch.log
timeout 120 python3 -m orchestrator.main \
  --config "${AGENT_ROOT}/config/agent.yaml" \
  --agent-root "${AGENT_ROOT}" \
  --inject-wav "${TEST_WAV}" \
  --no-partial \
  --no-tts \
  --log-level INFO > /tmp/phase_e_orch.log 2>&1 &
ORCH_PID=$!
sleep 2

echo "[2/3] WebSocket probe"
if ! python3 "${AGENT_ROOT}/scripts/ws_probe.py" --count 5 | tee /tmp/phase_e_ws.log; then
  echo "[fail] ws_probe failed"
  kill "${ORCH_PID}" 2>/dev/null || true
  tail -20 /tmp/phase_e_orch.log || true
  exit 1
fi
grep -q '"type":"hello"' /tmp/phase_e_ws.log || grep -q '"type": "hello"' /tmp/phase_e_ws.log || {
  echo "[fail] no hello frame"
  exit 1
}

wait "${ORCH_PID}" 2>/dev/null || true
grep -q "WebSocket ws://" /tmp/phase_e_orch.log || { echo "[fail] ws server not started"; exit 1; }
grep -q "asr_final" /tmp/phase_e_orch.log || { echo "[fail] pipeline incomplete"; exit 1; }
echo "[ok] WS + event pipeline passed"

echo ""
echo "[3/3] restart live orchestrator"
bash "${AGENT_ROOT}/scripts/start_orchestrator.sh"
echo "=== Phase E 完成 — ws://127.0.0.1:8765/ws ==="
