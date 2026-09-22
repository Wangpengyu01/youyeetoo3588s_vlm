#!/usr/bin/env python3
import os
import paramiko

PASS = os.environ.get("SSH196_PASS", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.100.196", username="gp", password=PASS, timeout=20)

cmds = [
    "docker exec youyeetoo bash -lc 'ls -la /home/youyeetoo/rk182x_sdk/rel_182x/rknn/rknn3-model-zoo/examples/InternVLM/cpp/'",
    "docker exec youyeetoo bash -lc 'cat /home/youyeetoo/rk182x_sdk/rel_182x/rknn/rknn3-model-zoo/examples/InternVLM/cpp/CMakeLists.txt 2>/dev/null | head -60'",
    "docker exec youyeetoo bash -lc 'find /home/youyeetoo/rk182x_sdk -iname \"*internvl*\" 2>/dev/null | head -40'",
    "docker exec youyeetoo bash -lc 'find /home/youyeetoo/rk182x_sdk -name \"*.cpp\" 2>/dev/null | xargs grep -l \"internvl3\" 2>/dev/null | head -15'",
    "find /home/gp/project/R1_SDK -iname '*internvl*' 2>/dev/null | head -40",
]
for cmd in cmds:
    print(">>>", cmd[:120])
    _, o, e = c.exec_command(cmd, timeout=300)
    print((o.read() + e.read()).decode(errors="replace")[:8000])
c.close()
