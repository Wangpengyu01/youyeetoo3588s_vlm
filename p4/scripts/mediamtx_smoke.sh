#!/bin/bash
# Quick smoke: local RTSP via MediaMTX + optional JPEG grab timing.
set -euo pipefail
P4_ROOT="${P4_ROOT:-/userdata/p4}"
AGENT="${AGENT_ROOT:-/userdata/agent}"
LOCAL_RTSP="rtsp://127.0.0.1:8554/cam"
OUT="${AGENT}/run/mediamtx_test.jpg"

echo "=== [mediamtx-smoke] ports ==="
ss -ltnp 2>/dev/null | grep -E '8554|8889' || netstat -ltnp 2>/dev/null | grep -E '8554|8889' || true

echo "=== [mediamtx-smoke] wait RTSP :8554 (30s) ==="
for i in $(seq 1 30); do
  if ss -ltnp 2>/dev/null | grep -q ':8554'; then
    break
  fi
  sleep 1
done

if ! ss -ltnp 2>/dev/null | grep -q ':8554'; then
  echo "[mediamtx-smoke] FAIL: 8554 not listening — tail ${P4_ROOT}/logs/mediamtx.log" >&2
  tail -30 "${P4_ROOT}/logs/mediamtx.log" 2>/dev/null || true
  exit 1
fi

echo "=== [mediamtx-smoke] grab ${LOCAL_RTSP} ==="
mkdir -p "$(dirname "${OUT}")"
rm -f "${OUT}"
t0=$(date +%s.%N)
if python3 -c "
import sys
sys.path.insert(0, '${AGENT}')
from pathlib import Path
from orchestrator.rtsp_frame import grab_rtsp_frame
ok = grab_rtsp_frame('${LOCAL_RTSP}', Path('${OUT}'), timeout=12.0, transport='tcp', size=448)
sys.exit(0 if ok else 1)
" 2>/dev/null; then
  t1=$(date +%s.%N)
  python3 -c "print('grab_sec=%.2f size=%d' % (${t1}-${t0}, __import__('pathlib').Path('${OUT}').stat().st_size))" 2>/dev/null || ls -lh "${OUT}"
  echo "[mediamtx-smoke] OK"
else
  echo "[mediamtx-smoke] grab failed — try: tail ${P4_ROOT}/logs/mediamtx.log" >&2
  tail -20 "${P4_ROOT}/logs/mediamtx.log" 2>/dev/null || true
  exit 1
fi

echo "=== [mediamtx-smoke] WHEP base (browser): http://$(hostname -I 2>/dev/null | awk '{print $1}'):8889/cam/whep ==="
