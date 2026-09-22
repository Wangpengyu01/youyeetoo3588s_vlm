#!/usr/bin/env python3
"""Pull InternVLM demo sources from 196 into agent/daemon/internvl_sdk/."""
import os
from pathlib import Path

import paramiko

PASS = os.environ.get("SSH196_PASS", "")
REMOTE_BASE = (
    "/home/gp/project/R1_SDK/rk182x_sdk/rel_182x/rknn/rknn3-model-zoo/examples/InternVLM/cpp"
)
OUT = Path(__file__).resolve().parents[1] / "daemon" / "internvl_sdk"
FILES = [
    "internvl3.cc",
    "internvl3.h",
    "main.cc",
    "CMakeLists.txt",
    "llm/rknn_internvl3_llm.cc",
    "llm/rknn_internvl3_llm.h",
    "vision/rknn_internvl3_vision.cc",
    "vision/rknn_internvl3_vision.h",
]

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.100.196", username="gp", password=PASS, timeout=20)
sftp = c.open_sftp()
OUT.mkdir(parents=True, exist_ok=True)
for rel in FILES:
    remote = f"{REMOTE_BASE}/{rel}".replace("/../", "/../")
    if rel.startswith("../"):
        remote = f"{REMOTE_BASE}/{rel}"
    local = OUT / rel.replace("../", "")
    local.parent.mkdir(parents=True, exist_ok=True)
    try:
        sftp.get(remote, str(local))
        print("ok", rel, local.stat().st_size)
    except Exception as exc:
        print("fail", rel, exc)
sftp.close()
c.close()
