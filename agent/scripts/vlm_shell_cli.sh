#!/bin/bash
# Terminal REPL — same core as WebUI (xiaolan_cli.brain). Prefer WebUI on PC; use on board HDMI TTY.
exec python3 -m xiaolan_cli repl --agent-root "${AGENT_ROOT:-/userdata/agent}"
