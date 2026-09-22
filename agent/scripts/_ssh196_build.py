#!/usr/bin/env python3
"""One-off: build vlm_daemon on 196 and adb push. Password via env SSH196_PASS only."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import paramiko

HOST = "192.168.100.196"
USER = "gp"
PASS = os.environ.get("SSH196_PASS", "")
REPO = Path(__file__).resolve().parents[2]


def run(client: paramiko.SSHClient, cmd: str, timeout: int = 600) -> tuple[int, str, str]:
    print(f"\n>>> {cmd[:200]}")
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    if out:
        print(out[-8000:] if len(out) > 8000 else out)
    if err:
        print(err[-4000:], file=sys.stderr)
    return code, out, err


def main() -> int:
    if not PASS:
        print("Set SSH196_PASS", file=sys.stderr)
        return 1

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS, timeout=20)

    run(client, "hostname && uname -m")
    code, out, _ = run(
        client,
        "find ~/project ~/youyeetoo -type d -name rknn3_session_test_demo 2>/dev/null | head -3",
    )
    session = out.strip().splitlines()[0] if out.strip() else ""
    _, out2, _ = run(
        client,
        "find ~/project ~ -name 'rknn_internvl3_demo.cpp' 2>/dev/null | head -3",
        timeout=300,
    )
    internvl_cpp = out2.strip().splitlines()[0] if out2.strip() else ""
    internvl_dir = str(Path(internvl_cpp).parent.parent) if internvl_cpp else ""

    if not session:
        _, o, _ = run(client, "docker ps --format '{{.Names}}' 2>/dev/null | head -5")
        if "youyeetoo" in o.lower() or o.strip():
            run(
                client,
                "docker exec youyeetoo find /home/youyeetoo -type d -name rknn3_session_test_demo 2>/dev/null | head -1",
                timeout=120,
            )

    # Under R1_SDK mount so `docker exec youyeetoo` sees REPO at /home/youyeetoo/_vlm_build
    remote = "/home/gp/project/R1_SDK/_vlm_build"
    run(client, f"mkdir -p {remote}/agent/daemon {remote}/agent/scripts")
    sftp = client.open_sftp()
    daemon = REPO / "agent" / "daemon"
    for name in (
        "vlm_daemon.cpp",
        "vlm_internvl_bridge.h",
        "vlm_internvl_bridge.cpp",
        "vlm_internvl_bridge_stub.cpp",
        "vlm_daemon_p5b.cmake",
        "CMakeLists.vlm_fragment",
    ):
        local = daemon / name
        sftp.put(str(local), f"{remote}/agent/daemon/{name}")
    build_sh = REPO / "agent" / "scripts" / "build_vlm_daemon_196.sh"
    sftp.put(str(build_sh), f"{remote}/agent/scripts/build_vlm_daemon_196.sh")
    sftp.close()
    run(client, f"sed -i 's/\\r$//' {remote}/agent/scripts/build_vlm_daemon_196.sh")

    if not session:
        code, o, _ = run(
            client,
            "find ~/project -type d -name rknn3_session_test_demo 2>/dev/null | head -1",
            timeout=300,
        )
        session = o.strip()

    docker_session = session.replace("/home/gp/project/R1_SDK", "/home/youyeetoo", 1)
    docker_repo = "/home/youyeetoo/_vlm_build"
    docker_internvl = (
        internvl_dir.replace("/home/gp/project/R1_SDK", "/home/youyeetoo", 1) if internvl_dir else ""
    )
    env = (
        f"export REPO={docker_repo} SESSION_DEMO={docker_session} "
        f"INTERNVL_DEMO={docker_internvl}"
    )
    build_cmd = (
        f"docker exec youyeetoo bash -lc '{env} && "
        f"bash {docker_repo}/agent/scripts/build_vlm_daemon_196.sh'"
    )
    code, _, _ = run(client, build_cmd, timeout=900)

    local_bin = REPO / "agent" / "bin" / "vlm_daemon"
    local_bin.parent.mkdir(parents=True, exist_ok=True)
    candidates = [
        f"{session}/vlm_daemon",
        f"{session}/build/build_RK3588_linux_aarch64_Release/vlm_daemon",
        f"{session}/install/rknn3_session_test_RK3588_Linux/vlm_daemon",
    ]
    pulled = False
    build_ok = code == 0
    sftp = client.open_sftp()
    if not build_ok:
        print("Build failed — not pulling stale binary", file=sys.stderr)
    for remote_bin in candidates:
        if not build_ok:
            break
        try:
            sftp.get(remote_bin, str(local_bin))
            print(f"Pulled {local_bin} from {remote_bin}")
            pulled = True
            break
        except OSError:
            continue
    if not pulled:
        _, o, _ = run(client, f"find {session} -name vlm_daemon -type f 2>/dev/null | head -1")
        if o.strip():
            sftp.get(o.strip().splitlines()[0], str(local_bin))
            print(f"Pulled {local_bin} from {o.strip().splitlines()[0]}")
            pulled = True
    sftp.close()

    client.close()
    return 0 if (build_ok and local_bin.is_file()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
