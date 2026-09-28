#!/usr/bin/env python3
import sys
import time
from pathlib import Path

sys.path.insert(0, "/userdata/agent")
from orchestrator.mediamtx_camera import MediamtxCameraConfig, grab_mediamtx_frame

c = MediamtxCameraConfig(grab_backend="mediamtx_whep")
t0 = time.monotonic()
ok = grab_mediamtx_frame(c, Path("/userdata/agent/run/mtx_combo.jpg"), timeout=12)
print("ok", ok, "sec", round(time.monotonic() - t0, 2))
