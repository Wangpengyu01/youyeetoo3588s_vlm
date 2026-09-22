#!/bin/bash
# Fix agent.yaml after mistaken global sed (asr/tts backend must not be vlm_daemon).
set -euo pipefail
CFG="${1:-/userdata/agent/config/agent.yaml}"
[[ -f "${CFG}" ]] || exit 1
if grep -q '^asr:' "${CFG}"; then
  sed -i '/^asr:/,/^[^ #]/ s/^  backend:.*/  backend: streaming_paraformer/' "${CFG}"
fi
if grep -q '^tts:' "${CFG}"; then
  sed -i '/^tts:/,/^[^ #]/ s/^  backend:.*/  backend: matcha/' "${CFG}"
fi
if grep -q '^inference:' "${CFG}"; then
  sed -i '/^inference:/,/^[^ #]/ s/^  backend:.*/  backend: vlm_daemon/' "${CFG}"
fi
echo "[repair] fixed backends in ${CFG}"
grep '^  backend:' "${CFG}" || true
