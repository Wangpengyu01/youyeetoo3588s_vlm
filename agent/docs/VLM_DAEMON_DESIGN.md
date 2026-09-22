# vlm_daemon 设计 · Spike 与落地路径

> 目标：在 RK1828 上 **单一常驻进程** 同时支持 **纯文字 chat** 与 **带图 see**，替代「`llm_daemon` + 每次 `rknn_internvl3_demo` 冷启动」双栈，消除看图时停 LLM、60s+ 卡顿。

## 1. 现状与问题

| 组件 | 加载 | 能力 | 问题 |
|------|------|------|------|
| `llm_daemon` | LLM 四件套 ~236MB | 流式 text chat | 无 vision |
| `rknn_internvl3_demo` | Vision+LLM 六件套 ~3GB | image + prompt → 一句 | 与 LLM 互斥；冷启动慢 |

Orchestrator 看图路径：`run_board_vlm.sh` → **stop llm_daemon** → `vlm_see.sh` → **start llm_daemon**。

## 2. vlm_daemon 目标形态

```
┌─────────────────────────────────────────────────────────┐
│ vlm_daemon (1828, 常驻)                                  │
│  · 六件套一次 load（vision rknn + llm rknn + tokenizer）   │
│  · 单 rknn3_session（或 vision/llm 双 session 同进程）     │
│  · Unix socket: /tmp/r1-vlm.sock（或复用 r1-llm.sock）    │
└─────────────────────────────────────────────────────────┘
         ▲ JSON Lines                    │
         │ chat / see / ping / clear     ▼ 流式 token
   orchestrator / llm_client 扩展
```

### 2.1 IPC（在 llm_daemon 协议上扩展）

**Client → vlm_daemon**

```json
{"type":"ping"}
{"type":"clear_history"}
{"type":"set_system_prompt","text":"你是小揽…"}
{"type":"chat","id":"t1","prompt":"主人你好","max_new_tokens":128}
{"type":"see","id":"v1","image_path":"/userdata/agent/run/latest_vlm.jpg","prompt":"桌上有什么？","max_new_tokens":128}
```

**规则**

- `chat`：**不传图** → 必须 **不跑 vision encoder**（Spike **S1** 判据：prefill 与 LLM-only 差距 &lt; 200ms）。
- `see`：读 JPEG → `frame_prepare` 同等逻辑（448 中心裁剪）→ vision prefill + LLM decode。
- 同一连接内多轮：保留 session KV / chat history（Spike **S2**）。

**Server → Client**（与现 llm_daemon 相同）

```json
{"type":"token","id":"…","text":"…"}
{"type":"done","id":"…","usage":{"prefill_ms":…,"generate_ms":…,"vision_ms":…}}
{"type":"error","id":"…","message":"…"}
```

### 2.2 实现策略（按风险排序）

| 阶段 | 做法 | 编译依赖 |
|------|------|----------|
| **Spike 0** | 板端脚本测 S1/S2/S3，**不新编 daemon** | 无 |
| **M1** |  fork `rknn_internvl3_demo` 主流程进 `vlm_daemon.cpp`，加 socket 循环 | RK1828 SDK + `rknn3_session_test_demo` + InternVL demo 源码 |
| **M2** | text-only 路径跳过 `vision encoder`（查 RKNN3 API / demo 分支） | 同上 |
| **M3** | orchestrator：`vlm_cmd` 改为 socket client；yaml `llm.socket_path` 指向 vlm | Python only |
| **M4** | systemd：`r1-vlm-daemon.service` **替换** `r1-llm-daemon` | 部署 |

**源码基线**

- Text：`agent/daemon/llm_daemon.cpp`（LLM-only session + JSONL）。
- Vision：`/userdata/rknn_InternVLM_demo/rknn_internvl3_demo` 对应 SDK 示例（六参数 + 图像路径 + prompt）。

## 3. Spike 实验（TECH_PLAN §4.1）

| ID | 实验 | 通过判据 | 板端脚本 |
|----|------|----------|----------|
| **S1** | 六件套 load 后 text-only | Prefill 比 LLM-only &lt; +200ms | `vlm_spike_s1_text_only.sh` |
| **S2** | text×3 → image×1 → text×1 | 无 Aborted · 回答连贯 | `vlm_spike_s2_multimodal.sh` |
| **S3** | 常驻 24h | `rknn-smi` 稳定 · 无 MODEL_SETUP fail | 手动 / cron |

**S1 不过** → P5b 退化为：**LLM daemon 常驻 + 按需 load VLM**（或 reboot 切换），与现网一致。

## 3.1 RK3588 上看图「无反应」的常见根因（非 VLM 慢）

在 adb 触发的脚本里调用 **`sudo systemctl stop r1-llm-daemon`** 时，进程可能进入 **D 状态**（不可中断 I/O），`timeout` 也杀不掉，表现为：

- 日志停在 `[S0c] run_board_vlm...` 或 `[coop-stop]...`
- `ps` 里出现 `sudo systemctl stop` 为 **D**

**规避：** `cooperative_stop_llm.sh` 只用 `systemctl kill` + `pkill` + 运行时 `Restart=no`，**禁止 systemctl stop**。仍异常时 **硬重启板子** 再测。

---

## 4. 编译机（192.168.100.191）现状（2026-09-23 探测）

| 项 | 结果 |
|----|------|
| 用户 `gp` / SSH | 可达 |
| `aarch64-linux-gnu-g++` | **未在 PATH** |
| 已解压 R1 SDK 树 | **无**（`~/project/1828sdk/` 仅 **tar/tgz 安装包**） |
| `rknn_internvl3_demo` 源码 | **未检出** |

**要在 191 上编译 vlm_daemon，需先：**

1. 解压 `RK1820_1828_RELEASE_V1.0.5B10.tar.gz`（或官方 Docker 交叉链环境，见 `BUILD_LINUX.md` 原 196 流程）。
2. 安装 / 启用 **aarch64-linux-gnu** 工具链。
3. 定位 `rknn_internvl3_demo` 与 `rknn3_session_test_demo` 源码树。
4. 将 `agent/daemon/vlm_daemon.cpp`（自 llm_daemon + demo 合并）放入 demo 目录按 Makefile 编出 **aarch64** 二进制。

**当前可立即执行：** 在 **R1 板端** 用现有 `llm_daemon` + `rknn_internvl3_demo` 跑 Spike 0，量化 S1/S2 可行性；编译待 SDK 解压后补跑。

## 5. orchestrator 对接（M3 预览）

```yaml
# agent.yaml（未来）
socket_path: /tmp/r1-vlm.sock   # 或兼容：llm_daemon 与 vlm_daemon 二选一
camera:
  vlm_mode: daemon              # daemon | script（script=现 run_board_vlm.sh）
```

- 纯文字：仍走 `_run_llm` → socket `chat`。
- 看图：`see` + 本地 `latest_vlm.jpg`，**不再** `systemctl stop r1-llm-daemon`。
- WebUI `_handle_direct_chat`：对 vision 意图走 `_handle_vision_turn`（与语音一致）。

## 6. 风险

- **显存**：六件套常驻 ~3GB 级，需实机 S3。
- **延迟**：带图 prefill 仍显著高于纯 text；靠 scene_memory / 后台低频刷新改善体验。
- **chat template**：InternVL 多轮需 `rknn3_session_set_chat_template`（Phase G-b），否则 S2「连贯」可能仅语义连贯、人设漂移。

## 7. M1 可测形态（2026-09）

| 入口 | 说明 |
|------|------|
| `vlm_shell_cli.sh` | **推荐**：socket → `llm_daemon` 聊天；看图 → cooperative + `vlm_cli_see.sh` |
| `vlm_daemon --cli` | 单进程 CLI；看图时 teardown LLM → `vlm_cli_see.sh` → 再 init（验证 handoff） |
| `vlm_daemon`（无 `--cli`） | 监听 `/tmp/r1-vlm.sock`，协议含 `see`（外调脚本，M2 改为进程内 vision） |

## 8. 下一步

1. 板端：`bash /userdata/agent/scripts/vlm_spike_s0_board.sh` 记录日志到 `logs/vlm_spike/`.
2. 196/191：编 `vlm_daemon`，板端试 `vlm_shell_cli.sh` 与 `--cli`。
3. 从 InternVL demo 抽六件套 init + in-process `see` → M2（text-only 跳过 vision encoder）。
4. S1–S3 全过 → 替换 systemd 与 orchestrator socket。
