#!/usr/bin/env bash
# Push voice scripts to board with Unix LF line endings (Windows CRLF breaks mic_arm seq).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BOARD="/userdata/voice/scripts"

if [ ! -d "${ROOT}/voice/scripts" ]; then
  ROOT="C:/Users/wwff/Documents/youyeetoo3588s"
fi

echo "[push-voice] ${ROOT}/voice/scripts -> ${BOARD}"

adb shell "mkdir -p ${BOARD}"

push_lf() {
  local src="$1"
  local dst="$2"
  local tmp
  tmp="$(mktemp)"
  tr -d '\r' < "${src}" > "${tmp}"
  adb push "${tmp}" "${dst}" >/dev/null
  rm -f "${tmp}"
}

for f in "${ROOT}/voice/scripts"/*; do
  [ -f "$f" ] || continue
  base="$(basename "$f")"
  push_lf "$f" "${BOARD}/${base}"
done

adb shell "chmod +x ${BOARD}/*.sh 2>/dev/null; sed -i 's/\\r$//' ${BOARD}/*.sh 2>/dev/null || true"
echo "[push-voice] done"
