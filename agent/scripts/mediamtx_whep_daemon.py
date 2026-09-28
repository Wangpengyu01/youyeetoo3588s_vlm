#!/usr/bin/env python3
"""Keep a WHEP session open; refresh mediamtx_latest.jpg for near-zero orchestrator grab latency."""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
from pathlib import Path

_AGENT = Path(os.environ.get("AGENT_ROOT", "/userdata/agent"))
sys.path.insert(0, str(_AGENT))

from orchestrator.mediamtx_camera import MediamtxCameraConfig  # noqa: E402
from orchestrator.whep_frame import grab_whep_frame_gst  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--whep", default=os.environ.get("MEDIAMTX_WHEP", "http://127.0.0.1:8889/cam/whep"))
    p.add_argument("--out", default="/userdata/agent/run/mediamtx_latest.jpg")
    p.add_argument("--interval", type=float, default=0.35)
    p.add_argument("--size", type=int, default=448)
    args = p.parse_args()
    out = Path(args.out)
    tmp = out.with_suffix(".part.jpg")
    out.parent.mkdir(parents=True, exist_ok=True)
    cfg = MediamtxCameraConfig(whep_url=args.whep, latest_frame=str(out))

    print(f"[whep-daemon] whep={args.whep} out={out} interval={args.interval}s", flush=True)
    while True:
        t0 = time.monotonic()
        ok = grab_whep_frame_gst(args.whep, tmp, timeout=15.0, size=args.size)
        if ok and tmp.is_file():
            shutil.move(str(tmp), str(out))
            print(f"[whep-daemon] ok dt={time.monotonic()-t0:.2f}s", flush=True)
        else:
            print(f"[whep-daemon] grab failed dt={time.monotonic()-t0:.2f}s", flush=True)
        time.sleep(max(0.05, args.interval))


if __name__ == "__main__":
    main()
