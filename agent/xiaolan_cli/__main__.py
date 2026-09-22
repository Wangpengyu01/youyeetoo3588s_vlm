"""python3 -m xiaolan_cli repl | serve"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> None:
    p = argparse.ArgumentParser(description="小揽 CLI — repl 或 serve（orchestrator+WS，供 WebUI）")
    p.add_argument("mode", choices=("repl", "serve"), help="repl=终端；serve=后台+WebSocket API")
    p.add_argument("--agent-root", default="/userdata/agent")
    p.add_argument("--config", default="/userdata/agent/config/agent.yaml")
    args, rest = p.parse_known_args()

    root = Path(args.agent_root)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    if args.mode == "repl":
        from xiaolan_cli.repl import main as repl_main

        raise SystemExit(repl_main(root))

    sys.argv = ["orchestrator.main", "--config", args.config, "--agent-root", str(root), *rest]
    from orchestrator.main import main as orch_main

    orch_main()


if __name__ == "__main__":
    main()
