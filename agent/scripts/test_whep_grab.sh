#!/bin/bash
set -euo pipefail
AGENT="${AGENT_ROOT:-/userdata/agent}"
OUT="${AGENT}/run/whep_test.jpg"
export PYTHONPATH="${AGENT}"
WHEP="${MEDIAMTX_WHEP:-http://127.0.0.1:8889/cam/whep}"
echo "[test] WHEP ${WHEP} -> ${OUT}"
python3 - <<PY
import sys, time
from pathlib import Path
sys.path.insert(0, "${AGENT}")
from orchestrator.whep_frame import grab_whep_frame_gst
t0 = time.monotonic()
ok = grab_whep_frame_gst("${WHEP}", Path("${OUT}"), timeout=18.0, size=448)
print("ok=", ok, "sec=", round(time.monotonic()-t0, 2), "size=", Path("${OUT}").stat().st_size if ok else 0)
sys.exit(0 if ok else 1)
PY
