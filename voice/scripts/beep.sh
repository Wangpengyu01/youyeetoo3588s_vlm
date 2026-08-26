#!/bin/bash
# Short beep before recording (play_wav handles route + warmup)
set -euo pipefail
BEEP=/tmp/beep.wav
espeak-ng -v zh -s 220 -a 200 -p 50 "滴" -w "${BEEP}" 2>/dev/null || {
  # fallback: 880Hz tone 200ms
  python3 - <<'PY'
import struct, math, wave
rate = 16000
dur = 0.25
freq = 880.0
n = int(rate * dur)
with wave.open("/tmp/beep.wav", "w") as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(rate)
    for i in range(n):
        v = int(24000 * math.sin(2 * math.pi * freq * i / rate))
        w.writeframes(struct.pack("<h", v))
PY
}
bash /userdata/voice/scripts/play_wav.sh "${BEEP}"
bash /userdata/voice/scripts/mic_setup.sh >/dev/null 2>&1 || true
sleep 0.15
