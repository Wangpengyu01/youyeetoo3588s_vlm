#!/usr/bin/env python3
import struct, math, sys
p = sys.argv[1] if len(sys.argv) > 1 else "/tmp/mic_test.wav"
with open(p, "rb") as f:
    f.read(44)
    data = f.read()
if len(data) < 2:
    print("NO_SAMPLES")
    sys.exit(1)
samples = struct.unpack("<%dh" % (len(data) // 2), data)
peak = max(abs(s) for s in samples)
rms = math.sqrt(sum(s * s for s in samples) / len(samples))
above500 = sum(1 for s in samples if abs(s) > 500)
above1000 = sum(1 for s in samples if abs(s) > 1000)
print(f"samples={len(samples)} peak={peak} rms={rms:.1f}")
print(f"above500={above500} ({100*above500/len(samples):.2f}%) above1000={above1000}")
if peak < 100:
    print("VERDICT: SILENCE - mic likely not routed or muted")
elif peak < 1000:
    if rms >= 25 or above500 > 0:
        print("VERDICT: SOFT_OK - level low but speech may ASR fine (monitor replay to check)")
    else:
        print("VERDICT: VERY_QUIET - increase mic gain or check routing")
else:
    print("VERDICT: SIGNAL_OK - mic hardware capturing audio")
