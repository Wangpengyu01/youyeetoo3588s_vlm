# P5b · 常驻 vlm_daemon（六件套合一）构建指南

目标：**一次 load** vision+LLM，`/tmp/r1-vlm.sock` 上 **chat**（纯文字）与 **see**（JPEG）无 cooperative 停 daemon、无 `rknn_internvl3_demo` 冷启动。

## 1. 构建机 192.168.100.196（gp / Docker youyeetoo）

与 `BUILD_LINUX.md` 相同环境，额外需要 **InternVL demo 源码树**（与板端 `/userdata/rknn_InternVLM_demo/rknn_internvl3_demo` 同版本）。

在 196 上 InternVL 源码（与板端 demo 同版）：

```text
rk182x_sdk/rel_182x/rknn/rknn3-model-zoo/examples/InternVLM/cpp/
  internvl3.cc · main.cc · llm/ · vision/
```

仓库内 bridge：`agent/daemon/vlm_internvl_bridge.cpp`（由 demo `main.cc` 抽出常驻逻辑）。  
CMake：`agent/daemon/vlm_daemon_p5b.cmake` 链 model-zoo `3rdparty` + `utils` + InternVL 源文件。

## 2. 同步仓库并编 vlm_daemon

在 **196** 上（仓库挂载进 Docker 后）：

```bash
export REPO=/path/to/youyeetoo3588s_vlm_upstream
export SESSION_DEMO=~/project/R1_SDK/rknn/rknn3-runtime/examples/rknn3_session_test_demo
export INTERNVL_DEMO=~/project/R1_SDK/.../rknn_InternVLM_demo   # 按 find 结果

bash "$REPO/agent/scripts/build_vlm_daemon_196.sh"
```

脚本会：

1. 拷贝 `agent/daemon/vlm_daemon.cpp`、`vlm_internvl_bridge*.cpp/h` → `$SESSION_DEMO/src/`
2. 若存在 `$INTERNVL_DEMO/src/*.cpp`，替换 **stub** 为真实 `vlm_internvl_bridge.cpp`（由 demo 主流程抽出，见 §4）
3. `make vlm_daemon`（Makefile 已含 fragment）

产物：`install/.../vlm_daemon` → push `/userdata/agent/bin/vlm_daemon`

## 3. 板端切换 P5b

```bash
adb push vlm_daemon /userdata/agent/bin/vlm_daemon
adb shell chmod +x /userdata/agent/bin/vlm_daemon
adb shell "sudo bash /userdata/agent/scripts/deploy_p5b_vlm_daemon.sh"
```

验证：

```bash
adb shell "python3 /userdata/agent/scripts/llm_client.py --socket /tmp/r1-vlm.sock --ping"
adb shell "python3 /userdata/agent/scripts/vlm_client_see.py /userdata/agent/run/camera_shot.jpg 描述画面"
```

## 4. 将 demo 接到 bridge（196 上一次性）

在 `rknn_internvl3_demo.cpp` 的 `main` 中已有：六路径 init、读 JPEG、vision latency、LLM decode。

抽取为 `vlm_internvl_bridge.cpp`（保留在 SDK 树或 patch）：

- `vlm_internvl_init` ← demo 里 load vision+llm + session
- `vlm_internvl_see` ← 单张 JPEG + prompt 推理
- `vlm_internvl_chat` ← **仅 LLM 路径**（S1：prefill 与 llm_daemon 差 &lt;200ms）
- `vlm_internvl_deinit` ← release

仓库内 **stub** 仅用于占位编译；**真实实现必须在 196 链 demo 对象**。

## 5. Spike 门禁

| ID | 命令 | 通过 |
|----|------|------|
| S1 | `vlm_spike_s1_text_only.sh` | text prefill ≤ LLM-only +200ms |
| S2 | 多轮 chat + see + chat | 无 Aborted |
| S3 | 24h 常驻 | rknn-smi 稳定 |

S1 不过 → 保留 `llm_daemon` + 脚本 VLM，不切换 systemd。

## 6. orchestrator / WebUI

`agent.yaml`:

```yaml
inference:
  backend: vlm_daemon   # llm_daemon | vlm_daemon
socket_path: /tmp/r1-vlm.sock
```

`xiaolan_cli.brain` 与 orchestrator 共用 socket，**see 不再调用 cooperative_stop_llm**。
