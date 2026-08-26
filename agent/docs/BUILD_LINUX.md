# llm_daemon 交叉编译（Linux VM）

在 **gp@192.168.100.196** R1 SDK Docker 内编译，产物 adb push 到板端。

## 1. 前提

- VM 已有 RKNN3 SDK 1.0.5b10 与 `rknn3_session_test_demo` 完整源码树（含 `Tokenizer.h`、`Makefile`）
- 板端已验收：`rknn3_session_test` LLM-only 可跑（P3）

典型 SDK 示例路径（按你 VM 实际调整）：

```text
~/r1-sdk/rknn/rknn3-runtime/examples/rknn3_session_test_demo/
├── Makefile
├── src/rknn3_session_test.cpp
├── include/Tokenizer.h
└── ...
```

## 2. 拷贝 daemon 源码

在 **PC** 仓库已含 `agent/daemon/llm_daemon.cpp`。传到 VM：

```bash
# PC → VM（示例）
scp agent/daemon/llm_daemon.cpp gp@192.168.100.196:~/r1-sdk/rknn/rknn3-runtime/examples/rknn3_session_test_demo/src/
```

或在 VM 内 `git clone` 你的 GitHub 仓库后复制：

```bash
cp ~/youyeetoo3588s_vlm/agent/daemon/llm_daemon.cpp \
   ~/r1-sdk/rknn/rknn3-runtime/examples/rknn3_session_test_demo/src/
```

## 3. 修改 Makefile（一次性）

在 `rknn3_session_test_demo/Makefile` 增加第二个目标，**或**单独一行编译：

```makefile
# 追加目标示例
llm_daemon: src/llm_daemon.cpp src/Tokenizer.cpp
	$(CXX) $(CXXFLAGS) $(INCLUDES) -o llm_daemon $^ $(LDFLAGS) $(LIBS)
```

若不想改 Makefile，Docker 内手动编译（路径按 SDK 调整）：

```bash
cd ~/r1-sdk/rknn/rknn3-runtime/examples/rknn3_session_test_demo

export RKNN3_API_PATH=../../rknn3-api
export CXX=aarch64-linux-gnu-g++

$aarch64-linux-gnu-g++ -O2 -std=c++17 \
  -I./include -I${RKNN3_API_PATH}/include \
  -o llm_daemon \
  src/llm_daemon.cpp src/Tokenizer.cpp \
  -L${RKNN3_API_PATH}/lib/aarch64 -lrknn3_api \
  -lpthread -ldl
```

> 若 `Tokenizer.cpp` 路径不同，以 SDK demo 目录现有 `Makefile` 为准，**与编 rknn3_session_test 相同 flags**。

## 4. 编译

```bash
# Docker 内
make llm_daemon
# 或 make 后手动 g++（见上）

file llm_daemon
# 期望: ELF 64-bit LSB executable, ARM aarch64
```

## 5. 推到板端

```bash
# VM → 板（adb 连 PC 时可在 PC 上 pull 再 push）
adb push llm_daemon /userdata/agent/bin/llm_daemon
adb shell chmod +x /userdata/agent/bin/llm_daemon
```

PC 端也可：

```powershell
adb push agent\bin\llm_daemon /userdata/agent/bin/llm_daemon
```

## 6. 板端验收

```bash
# 推送脚本（PC）
powershell -File agent/scripts/push_agent.ps1

adb shell
bash /userdata/agent/scripts/start_llm_daemon.sh
bash /userdata/agent/scripts/phase_a_test.sh
```

单客户端测试：

```bash
python3 /userdata/agent/scripts/llm_client.py --ping
python3 /userdata/agent/scripts/llm_client.py --prompt "你好，请用一句话介绍你自己。"
```

## 7. 通过判据（Phase A）

| 项 | 判据 |
|----|------|
| 启动 | `/tmp/r1-llm.sock` 存在 · `rknn-smi` 显存 ~236MB 级 |
| ping | `{"type":"pong"}` |
| 单轮 | 流式 token · `done.prefill_ms` < 500ms（daemon 已热） |
| 多轮 | 第二问能引用上下文 |
| 对比 | 同 prompt · 比 `llm_ask.py` 每轮快 **一个数量级** |

## 8. 故障

| 现象 | 处理 |
|------|------|
| `No RK182X devices` | 冷启 `adb reboot` · 勿 manual restart rknn3 |
| init failed | 检查四件套路径 · `rknn-smi info` |
| `RKNN3_QUERY_LLM_CONFIG, size = 184, expect 408` | **头文件与板端 runtime 不一致**。必须用与 `/usr/bin/rknn3_session_test` 同一套 `rknn3-api/include` 重编；编完可在 VM 跑 `echo 'sizeof check' && grep -r rknn3_api.h ${RKNN3_API_PATH}/include` |
| socket 无响应 | `tail -f /userdata/agent/logs/llm_daemon.log` |

### API 版本自检（VM 编译前）

板端 `rknn3_session_test` 能跑时，头文件里的 `sizeof(rknn3_llm_config)` 应为 **408**（1.0.5b10 当前板端）。若你编出的 `llm_daemon` 日志里是 `size=184, expect=408`，说明用了**旧版** `rknn3_api.h`，请改用：

```bash
export RKNN3_API_PATH=~/project/RK182X/rknn/rknn3-api   # 与 session_test_demo Makefile 一致
grep -n rknn3_llm_config ${RKNN3_API_PATH}/include/rknn3_api.h
make clean && make llm_daemon
```

---

## 9. 何时必须重编 llm_daemon · Phase G-b（chat template）

> **当前仓库状态（2026-08-26）**  
> - Python 编排层（`orchestrator`）已把 `agent.yaml` 的 `system_prompt` **拼进每轮 prompt 字符串**发给 daemon。  
> - `agent/daemon/llm_daemon.cpp` **尚未**调用 `rknn3_session_set_chat_template`，模型常忽略「小揽」等人设。  
> - 应用层已用 `persona_reply_for()` 兜底；**要让提示词真正生效，必须重编 daemon 并启用 chat template**（Phase G-b）。

### 9.1 必须重编的情况

| 场景 | 是否重编 |
|------|----------|
| 只改 Python / yaml / 语音脚本 | **否** — `push_agent.ps1` 即可 |
| 修改了 `agent/daemon/llm_daemon.cpp` | **是** |
| 要启用 InternVL ChatML template（推荐） | **是** |
| 板端日志 `size=184, expect=408` | **是** — 换对齐的 `rknn3-api` 头文件后重编 |
| 仓库里的 `agent/bin/llm_daemon` 与 VM 新编产物不一致 | **是** — 以 VM 编译产物为准 push |

### 9.2 源码改动要点（你在 VM 里做）

在 `init_daemon()` 里、`rknn3_session_set_kvcache_policy` **之后**增加（token 名以 GGUF 为准，InternVL3.5 一般为 ChatML）：

```cpp
  // Phase G-b: InternVL ChatML — system 留空，由 orchestrator 每轮 prompt 携带规则（或后续 IPC 注入）
  {
    const char *system_prompt =
        "<|im_start|>system\n你是 youyeetoo R1 语音助手小揽，只用简体中文简短回答。\n";
    const char *prompt_prefix = "<|im_start|>user\n";
    const char *prompt_postfix = "\n<|im_start|>assistant\n";
    ret = rknn3_session_set_chat_template(g_session, system_prompt, prompt_prefix, prompt_postfix);
    if (ret != RKNN3_SUCCESS) {
      fprintf(stderr, "[daemon] set_chat_template failed ret=%d\n", ret);
      return -1;
    }
    fprintf(stderr, "[daemon] chat template enabled (InternVL ChatML)\n");
  }
```

> 若 `set_chat_template` 返回非 0，在板子或 PC 上对 tokenizer 查真实模板：  
> `python3 read_gguf.py /userdata/models/InternVL3_5-4B/InternVL3_5-4B.tokenizer.gguf`  
> 把 `im_start` / `im_end` 特殊 token 与上面对齐（SDK 示例里写作 `<|im_end|>` 处应对应 ``）。

启用 template 后，orchestrator 侧 **建议** 只发用户 ASR 文本（不再重复拼 system）；当前版本仍发合并 prompt 也能跑，但可能双重 system — Phase G-b 后续可改 `orchestrator/main.py` 的 `_run_llm()`。

### 9.3 重编与部署（完整流程）

```bash
# ── 1. PC：拉最新代码 ──
git pull origin main

# ── 2. PC → VM：同步 daemon 源码 ──
scp agent/daemon/llm_daemon.cpp \
  gp@192.168.100.196:~/r1-sdk/rknn/rknn3-runtime/examples/rknn3_session_test_demo/src/

# ── 3. VM Docker 内编译（flags 与 rknn3_session_test 完全一致）──
ssh gp@192.168.100.196
cd ~/r1-sdk/rknn/rknn3-runtime/examples/rknn3_session_test_demo
export RKNN3_API_PATH=~/project/RK182X/rknn/rknn3-api   # 与板端 session_test 同版本
make clean && make llm_daemon
file llm_daemon    # 必须是 ELF 64-bit ARM aarch64

# ── 4. VM → PC（或直接 adb push）──
# scp gp@192.168.100.196:.../llm_daemon  ./agent/bin/llm_daemon

# ── 5. PC → 板端 ──
adb push agent/bin/llm_daemon /userdata/agent/bin/llm_daemon
adb shell chmod +x /userdata/agent/bin/llm_daemon

# ── 6. 板端：重启 daemon + orchestrator ──
adb shell bash -c '
  pkill -f llm_daemon || true
  pkill -f orchestrator.main || true
  rm -f /tmp/r1-llm.sock /userdata/agent/run/*.pid
  bash /userdata/agent/scripts/start_llm_daemon.sh
  bash /userdata/agent/scripts/start_orchestrator.sh
'
```

### 9.4 验收（重编后）

```bash
# 日志应出现 chat template enabled
adb shell tail -30 /userdata/agent/logs/llm_daemon.log

# 问「你叫什么名字」— 应优先回答「小揽」，而不是「人工智能助手」
adb shell tail -f /userdata/agent/logs/orchestrator.log
# 期望：LLM 正文含「小揽」；若仍机器人腔，persona fallback 仍会兜底
```

| 判据 | 通过 |
|------|------|
| daemon 启动 | log 含 `[daemon] chat template enabled` |
| socket | `/tmp/r1-llm.sock` 存在 |
| 人设 | 问名字 → 口播含「小揽」（LLM 或 fallback） |
| 性能 | 首 token 仍 < 500ms（daemon 已热） |

**不需要重编 llm_daemon 时**：仅 Python/yaml 变更 → `powershell -File agent/scripts/push_agent.ps1` + 重启 orchestrator 即可。
