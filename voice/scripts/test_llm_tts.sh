#!/bin/bash
# One-shot end-to-end test: fixed prompt (no mic needed for LLM/TTS path)
set -euo pipefail
source /userdata/voice/scripts/voice_env.sh
SCRIPTS=/userdata/voice/scripts

PROMPT="${1:-你好，请用一句话介绍你自己。}"

echo "[TEST] prompt: ${PROMPT}"
echo "[LLM] ..."
REPLY=$(python3 "${SCRIPTS}/llm_ask.py" "${PROMPT}")
echo "[LLM] ${REPLY}"
echo "[TTS] ..."
"${SCRIPTS}/tts.sh" "${REPLY}"
echo "[TEST] done"
