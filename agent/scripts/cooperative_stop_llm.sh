#!/bin/bash
# Stop llm_daemon for VLM. Use from adb shell (root): NO sudo — sudo+systemctl → D-state on RK3588.
set -eu

echo "[coop-stop] kill llm_daemon (no sudo)..."

pkill -TERM -f '/userdata/agent/bin/llm_daemon' 2>/dev/null || true
for _ in $(seq 1 30); do
  pgrep -f '/userdata/agent/bin/llm_daemon' >/dev/null 2>&1 || break
  sleep 0.2
done

if pgrep -f '/userdata/agent/bin/llm_daemon' >/dev/null 2>&1; then
  pkill -KILL -f '/userdata/agent/bin/llm_daemon' 2>/dev/null || true
  sleep 0.5
fi

if pgrep -f '/userdata/agent/bin/llm_daemon' >/dev/null 2>&1; then
  echo "[coop-stop] FAIL: llm still running — reboot board" >&2
  exit 1
fi

rm -f /tmp/r1-llm.sock 2>/dev/null || true
echo "[coop-stop] ok (note: systemd may respawn llm ~10s unless stopped from local console)"
exit 0
