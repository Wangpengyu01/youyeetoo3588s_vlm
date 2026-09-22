#!/bin/bash
# On gp@192.168.100.196: locate InternVL demo + session_test demo for P5b build.
set -eu

SDK="${R1_SDK:-$HOME/project/R1_SDK}"
echo "[196] SDK root: ${SDK}"

echo "=== rknn3_session_test_demo ==="
find "${SDK}" -type d -name 'rknn3_session_test_demo' 2>/dev/null | head -3

echo "=== InternVL demo / rknn_internvl3_demo.cpp ==="
find "${SDK}" \( -name 'rknn_internvl3_demo.cpp' -o -name 'rknn_InternVLM_demo' \) 2>/dev/null | head -10

echo ""
echo "Export then build:"
echo "  export REPO=\$(pwd)/youyeetoo3588s_vlm_upstream"
echo "  export SESSION_DEMO=${SDK}/rknn/rknn3-runtime/examples/rknn3_session_test_demo"
echo "  export INTERNVL_DEMO=<path from find above>"
echo "  bash \$REPO/agent/scripts/build_vlm_daemon_196.sh"
