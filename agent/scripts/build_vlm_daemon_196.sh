#!/bin/bash
# Run on 192.168.100.196 inside youyeetoo Docker (R1_SDK mounted at /home/youyeetoo).
# Builds aarch64 vlm_daemon (P5b) via CMake + InternVLM model-zoo sources.
set -euo pipefail

REPO="${REPO:-$HOME/youyeetoo3588s_vlm_upstream}"
SESSION_DEMO="${SESSION_DEMO:-$HOME/project/R1_SDK/rk182x_sdk/rel_182x/rknn/rknn3-runtime/examples/rknn3_session_test_demo}"

if [ ! -d "$SESSION_DEMO/src" ]; then
  echo "Missing SESSION_DEMO=$SESSION_DEMO" >&2
  exit 1
fi

DAEMON_SRC="$REPO/agent/daemon"
echo "[build] sync daemon sources → $SESSION_DEMO/src/"
cp -f "$DAEMON_SRC/vlm_daemon.cpp" "$SESSION_DEMO/src/"
cp -f "$DAEMON_SRC/vlm_internvl_bridge.h" "$SESSION_DEMO/src/"
if [ -f "$DAEMON_SRC/vlm_internvl_bridge.cpp" ]; then
  cp -f "$DAEMON_SRC/vlm_internvl_bridge.cpp" "$SESSION_DEMO/src/"
else
  echo "[build] fallback stub bridge" >&2
  cp -f "$DAEMON_SRC/vlm_internvl_bridge_stub.cpp" "$SESSION_DEMO/src/vlm_internvl_bridge.cpp"
fi
cp -f "$DAEMON_SRC/vlm_daemon_p5b.cmake" "$SESSION_DEMO/vlm_daemon_p5b.cmake"

CMAKE="$SESSION_DEMO/CMakeLists.txt"
MARKER="# install target and libraries"

python3 - "$CMAKE" "$MARKER" <<'PY'
import re, sys
cmake, marker = sys.argv[1], sys.argv[2]
text = open(cmake, encoding="utf-8", errors="replace").read()
text = re.sub(
    r"\n# --- P5b vlm_daemon.*?\nvlm_daemon:.*?\n",
    "\n",
    text,
    flags=re.S,
)
text = re.sub(
    r"\n# vlm_daemon — P5b unified.*?\nendif\(\)\n",
    "\n",
    text,
    flags=re.S,
)
text = re.sub(
    r"\n# P5b vlm_daemon \(see vlm_daemon_p5b\.cmake\)\ninclude\(.*vlm_daemon_p5b\.cmake\)\n",
    "\n",
    text,
)
if "vlm_daemon_p5b.cmake" not in text:
    text = text.replace(
        marker,
        'include(${CMAKE_CURRENT_SOURCE_DIR}/vlm_daemon_p5b.cmake)\n\n' + marker,
        1,
    )
open(cmake, "w", encoding="utf-8").write(text)
PY

if grep -q 'add_executable(vlm_daemon' "$CMAKE" && ! grep -q 'vlm_daemon_p5b.cmake' "$CMAKE"; then
  echo "[build] WARN: CMakeLists still has inline vlm_daemon; edit manually" >&2
fi
if ! grep -q 'install(TARGETS vlm_daemon' "$CMAKE"; then
  sed -i '/install(TARGETS llm_daemon DESTINATION/a install(TARGETS vlm_daemon DESTINATION ./)' "$CMAKE"
fi

BUILD_DIR="${SESSION_DEMO}/build/build_RK3588_linux_aarch64_Release"
if [ ! -d "$BUILD_DIR" ]; then
  echo "[build] no $BUILD_DIR — run build-linux.sh -t rk3588 -a aarch64 -b Release first" >&2
  exit 1
fi

cd "$BUILD_DIR"
echo "[build] cmake + make vlm_daemon in $BUILD_DIR"
cmake ../..
make -j"$(nproc 2>/dev/null || echo 4)" vlm_daemon

OUT="${BUILD_DIR}/vlm_daemon"
cp -f "$OUT" "${SESSION_DEMO}/vlm_daemon"
file "${SESSION_DEMO}/vlm_daemon"
echo "[build] OK → ${SESSION_DEMO}/vlm_daemon"
