#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path("/userdata/agent")))
from orchestrator.config_loader import load_yaml

c = load_yaml("/userdata/agent/config/agent.yaml")
a = c.get("asr") or {}
print("asr.backend=", repr(a.get("backend")))
print("inference=", c.get("inference"))
