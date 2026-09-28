#!/bin/bash
# Compare grab latency on board; prints RECOMMENDED_GRAB_BACKEND=...
set -euo pipefail
AGENT="${AGENT_ROOT:-/userdata/agent}"
export PYTHONPATH="${AGENT}"
P4="${P4_ROOT:-/userdata/p4}"
# shellcheck disable=SC1091
source "${P4}/scripts/p4_env.sh" 2>/dev/null || true

python3 - <<'PY'
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, "/userdata/agent")
from orchestrator.mediamtx_camera import MediamtxCameraConfig, grab_mediamtx_frame, _copy_if_fresh
from orchestrator.rtsp_frame import grab_rtsp_frame

RUNS = 3
OUT = Path("/userdata/agent/run/bench_grab.jpg")
CAM_DIRECT = __import__("os").environ.get("RTSP_URL", "rtsp://192.168.2.169:554/stream_2")


def bench(name, fn):
    times = []
    ok_n = 0
    for i in range(RUNS):
        t0 = time.monotonic()
        try:
            ok = fn()
        except Exception as e:
            print(f"{name} run{i+1} error: {e}")
            ok = False
        dt = time.monotonic() - t0
        if ok:
            ok_n += 1
            times.append(dt)
            print(f"{name} run{i+1}: {dt:.3f}s ok size={OUT.stat().st_size if OUT.is_file() else 0}")
        else:
            print(f"{name} run{i+1}: FAIL {dt:.3f}s")
    if not times:
        return name, None, 0
    return name, statistics.mean(times), ok_n


results = []

cfg_cache = MediamtxCameraConfig(grab_backend="mediamtx_whep")
latest = Path(cfg_cache.latest_frame)


def try_cache():
    return _copy_if_fresh(latest, OUT, cfg_cache.cache_max_age_sec)


results.append(bench("cache_mediamtx_latest", try_cache))

cfg_whep = MediamtxCameraConfig(grab_backend="mediamtx_whep")


def try_whep_chain():
    if OUT.exists():
        OUT.unlink()
    return grab_mediamtx_frame(cfg_whep, OUT, timeout=15, size=448)


results.append(bench("mediamtx_whep_chain", try_whep_chain))

cfg_rtsp = MediamtxCameraConfig(grab_backend="mediamtx_rtsp")


def try_mtx_rtsp():
    if OUT.exists():
        OUT.unlink()
    return grab_mediamtx_frame(cfg_rtsp, OUT, timeout=12, size=448)


results.append(bench("mediamtx_local_rtsp", try_mtx_rtsp))


def try_direct():
    if OUT.exists():
        OUT.unlink()
    return grab_rtsp_frame(CAM_DIRECT, OUT, timeout=18, transport="tcp", size=448)


results.append(bench("camera_direct_rtsp", try_direct))

print("\n=== summary (mean of successful runs) ===")
ranked = []
for name, mean, ok_n in results:
    if mean is None:
        print(f"  {name}: FAILED")
        continue
    print(f"  {name}: mean={mean:.3f}s ok={ok_n}/{RUNS}")
    ranked.append((mean, name))

ranked.sort()
if not ranked:
    print("RECOMMENDED_GRAB_BACKEND=rtsp")
    sys.exit(1)

best_mean, best_name = ranked[0]
mapping = {
    "cache_mediamtx_latest": "mediamtx_whep",
    "mediamtx_whep_chain": "mediamtx_whep",
    "mediamtx_local_rtsp": "mediamtx_rtsp",
    "camera_direct_rtsp": "rtsp",
}
rec = mapping.get(best_name, "mediamtx_whep")
print(f"\nRECOMMENDED_GRAB_BACKEND={rec}")
print(f"# fastest_sample={best_name} mean_sec={best_mean:.3f}")
print("NOTE: enable mediamtx_rtsp_frame_daemon.sh for cache_mediamtx_latest to win consistently.")
PY
