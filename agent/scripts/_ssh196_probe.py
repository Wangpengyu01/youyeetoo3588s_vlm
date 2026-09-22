#!/usr/bin/env python3
import os, paramiko
PASS = os.environ.get("SSH196_PASS", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.100.196", username="gp", password=PASS, timeout=20)

def run(cmd):
    print(">>>", cmd)
    _, o, e = c.exec_command(cmd, timeout=180)
    out = (o.read() + e.read()).decode(errors="replace")
    print(out)

run("docker ps -a --format '{{.Names}} {{.Status}}'")
run("which make || true")
run("docker exec youyeetoo bash -lc 'which make; pwd; ls -la /home/youyeetoo 2>/dev/null | head'")
run(
    "docker exec youyeetoo bash -lc "
    "'find /home/youyeetoo -type d -name rknn3_session_test_demo 2>/dev/null | head -3'"
)
run(
    "docker exec youyeetoo bash -lc "
    "'find /home/youyeetoo -name rknn_internvl3_demo.cpp 2>/dev/null | head -5'"
)
run(
    "docker exec youyeetoo bash -lc "
    "'ls /home/youyeetoo/rk182x_sdk/rel_182x/rknn/rknn3-runtime/examples/rknn3_session_test_demo/src | head -20'"
)
run(
    "docker exec youyeetoo bash -lc "
    "'grep -E \"llm_daemon|Tokenizer|TARGET\" "
    "/home/youyeetoo/rk182x_sdk/rel_182x/rknn/rknn3-runtime/examples/rknn3_session_test_demo/Makefile | head -30'"
)
run(
    "docker exec youyeetoo bash -lc "
    "'find /home/youyeetoo/rk182x_sdk -name Tokenizer.cpp 2>/dev/null | head -5'"
)
run(
    "docker exec youyeetoo bash -lc "
    "'wc -l /home/youyeetoo/rk182x_sdk/rel_182x/rknn/rknn3-runtime/examples/rknn3_session_test_demo/Makefile; "
    "ls -la /home/youyeetoo/rk182x_sdk/rel_182x/rknn/rknn3-runtime/examples/rknn3_session_test_demo/Makefile*'"
)
run(
    "docker exec youyeetoo bash -lc "
    "'ls /home/youyeetoo/rk182x_sdk/rel_182x/rknn/rknn3-runtime/examples/rknn3_session_test_demo/install 2>/dev/null | head'"
)
run(
    "docker exec youyeetoo bash -lc "
    "'file /home/youyeetoo/rk182x_sdk/rel_182x/rknn/rknn3-runtime/examples/rknn3_session_test_demo/llm_daemon 2>/dev/null; "
    "find /home/youyeetoo/rk182x_sdk/rel_182x/rknn/rknn3-runtime/examples/rknn3_session_test_demo -name llm_daemon -type f'"
)
run("docker inspect youyeetoo --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{println}}{{end}}'")
run(
    "docker exec youyeetoo bash -lc "
    "'grep -n llm_daemon /home/youyeetoo/rk182x_sdk/rel_182x/rknn/rknn3-runtime/examples/rknn3_session_test_demo/CMakeLists.txt'"
)
run(
    "docker exec youyeetoo bash -lc "
    "'sed -n \"1,120p\" /home/youyeetoo/rk182x_sdk/rel_182x/rknn/rknn3-runtime/examples/rknn3_session_test_demo/CMakeLists.txt'"
)
c.close()
