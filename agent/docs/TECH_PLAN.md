# P5 智能体技术方案

> **版本：** v1.0 · 2026-08-26  
> **状态：** ✅ 已锁定 — v1 实施 + 并行 VLM spike

---

## 摘要

v1 在 R1 上交付 **Ollama 式 LLM 常驻服务 + 流式语音对话**：3588 负责 VAD/ASR/TTS/编排，1828 常驻 **InternVL3.5-4B LLM-only**（不加载 vision）。用户说完后 **2–4s 内听到首句回复**。`see()` 与统一 VLM daemon **不在 v1**；并行做 board spike，通过后 P5b 合并为单一 `vlm_daemon`。

---

## 1. 常驻模型规格（llm_daemon）

### 1.1 模型身份

| 项 | 值 |
|----|-----|
| **产品名** | InternVL3.5-4B（Intern-S1 系列对话能力） |
| **部署形态** | **LLM-only** · RKNN3 W4A16 · **不加载 vision encoder** |
| **Runtime** | RKNN3 API **1.0.5b10** · RM1828 EP |
| **用途** | 纯文本多轮 chat（v1 唯一 1828 常驻模型） |

> ⚠️ **不是** Ollama/GGUF；**不是** `rknn_internvl3_demo` 六件套；**不是** Qwen3-VL。  
> 与 P3 验收相同路径：`rknn3_session_test` 仅 llm 四件套。

### 1.2 板端文件（四件套）

目录：`/userdata/models/InternVL3_5-4B/`

| 文件 | 说明 |
|------|------|
| `llm_InternVL3_5-4B.rknn` | LLM 结构 |
| `llm_InternVL3_5-4B.weight` | LLM 权重 |
| `InternVL3_5-4B.tokenizer.gguf` | 分词 + chat template |
| `InternVL3_5-4B.embed.bin` | 词嵌入表 |

**不加载（v1 llm_daemon）：**

| 文件 | 说明 |
|------|------|
| `vision_InternVL3_5-4B.rknn` | Vision encoder · P5b / spike 用 |
| `vision_InternVL3_5-4B.weight` | Vision 权重 · P5b / spike 用 |

### 1.3 推理参数（冻结默认值）

| 参数 | 值 | 说明 |
|------|-----|------|
| `max_context_len` | **1024** | 与 P3 session_test 一致 |
| `max_new_tokens` | **64** | 控制 TTS 时长 · 可 IPC 覆盖 |
| `core_mask` | **0xff** | 1828 全核 |
| `keep_history` | **1** | 多轮 KV cache |
| `max_history_turns` | **8–10** | 超出滑动截断 |
| `thinking` | **关** | session 路径无 thinking |

### 1.4 资源与性能（P3 实测基准）

| 指标 | LLM-only 常驻 | 全 VLM 六件套 |
|------|---------------|---------------|
| 1828 显存 | **~236 MB** | **~3 GB+** |
| 冷加载 | 数秒级（daemon 仅一次） | ~25–35 s |
| Prefill | ~120–150 ms | + Vision ~190 ms |
| Generate | **~80 tok/s** | 相近 |
| 纯聊天 | ✅ v1 选用 | ⚠️ stock demo 每轮过 vision |

### 1.5 源码与二进制

| 项 | 路径 |
|----|------|
| Fork 基线 | `voice/src/rknn3_session_test.cpp` |
| 目标二进制 | `/userdata/agent/bin/llm_daemon` |
| 废弃 | `llm_ask.py` binary patch · 每轮 subprocess |

### 1.6 启动命令（等价 · daemon 内部一次执行）

```bash
# llm_daemon 启动时等价于：
rknn3_session_test \
  /userdata/models/InternVL3_5-4B/llm_InternVL3_5-4B.rknn \
  /userdata/models/InternVL3_5-4B/llm_InternVL3_5-4B.weight \
  /userdata/models/InternVL3_5-4B/InternVL3_5-4B.tokenizer.gguf \
  /userdata/models/InternVL3_5-4B/InternVL3_5-4B.embed.bin \
  1024 64 0xff
# 差异：进程不退出 · Unix socket · result_callback 流式 · 动态 prompt
```

---

## 2. v1 范围

### 包含

- [x] **llm_daemon** — InternVL3.5-4B LLM-only 1828 常驻（Ollama 式）
- [x] **orchestrator** — Python 3 asyncio 状态机
- [x] **VAD** — 始终监听 + 端点检测
- [x] **ASR** — 3588 CPU · sherpa-onnx 本地（online 流式，并行验证 offline fallback）
- [x] **分句 TTS** — 3588 CPU · VITS-melo · 应用层伪流式（非 NPU）
- [x] **agent.yaml** — system_prompt / 人设 · 无需微调
- [x] **agent_api** — HTTP/WebSocket 占位（HDMI 触屏后排）

### 不包含（v1）

- [ ] `see()` / RTSP 看图进对话
- [ ] 统一 `vlm_daemon`（待 spike 通过后 P5b）
- [ ] HDMI 触屏 UI 实现
- [ ] 唤醒词 · barge-in · 模型微调

---

## 3. 架构

```
RK3588S                           RM1828 (RK1828)
────────                          ───────────────
Mic → VAD → sherpa ASR (CPU)      llm_daemon (RKNN3)
       ↓                                ↑
orchestrator (asyncio) ──/tmp/r1-llm.sock──┘
       ↓                         InternVL3.5-4B
分句 → VITS TTS (CPU) → play_wav   LLM-only ~236MB
       ↓
J368 喇叭

agent_api :8765 (WebSocket 预留 · HDMI 触屏 P5c)
```

| 模块 | 语言 | 芯片 | 职责 |
|------|------|------|------|
| `llm_daemon` | C++ | 1828 | 加载 llm 四件套 · 流式 token · 多轮 history |
| `orchestrator` | Python | 3588 | IDLE/LISTEN/ASR/LLM/TTS 状态机 |
| `asr_stream` | Python + sherpa | 3588 CPU | online ASR + VAD 端点 |
| `tts_queue` | Python + sherpa | 3588 CPU | 分句合成 + play_wav route guard |
| `agent_api` | Python | 3588 | WS 事件推送 · 触屏预留 |
| `voice_hw_board.sh` | shell | 3588 | 冻结 mic/speaker 配置 · 复用 |

**算力说明：** ASR/TTS **不用 3588 NPU**；v1 继续 sherpa-onnx **CPU**（已验收）。1828 **仅 LLM RKNN3**。

---

## 4. 演进路径：v1 → P5b 统一 VLM

| 阶段 | 1828 常驻 | 看图 |
|------|-----------|------|
| **v1（当前）** | `llm_daemon` LLM-only ~236MB | ❌ · 仍可用 `p4_test.sh` 手动 |
| **并行 spike** | 不影响 v1 | 验证统一 VLM 可行性 |
| **P5b（spike 通过后）** | 可选升级为 `vlm_daemon` 六件套 ~3GB | ✅ chat + see 同一 Session |

**不在 v1 维护两套模型并行运行**；v1 只常驻 LLM。spike 通过后 **替换** 为统一 `vlm_daemon`，而非 long-term 双 daemon。

### 4.1 VLM 统一常驻 Spike（与 v1 并行）

| # | 实验 | 通过判据 |
|---|------|----------|
| S1 | 六件套 load 后 **text-only 不跑 vision encoder** | Prefill 与 LLM-only 差距 < 200ms |
| S2 | 同 Session：text×3 → image×1 → text×1 | 上下文连贯 · 无 Aborted |
| S3 | 常驻 24h · `rknn-smi` | 显存稳定 · 无 MODEL_SETUP fail |

- **S1–S3 全过** → P5b 改为单一 `vlm_daemon`（chat + see）
- **S1 不过** → P5b 保留 LLM daemon + 按需 load VLM（或 reboot 切换）

---

## 5. IPC 协议

Socket：`/tmp/r1-llm.sock` · JSON Lines · 类似 Ollama `/api/chat` 语义

### Client → llm_daemon

```json
{"type":"chat","id":"req-1","prompt":"你好","max_new_tokens":64}
{"type":"set_system_prompt","text":"你是 R1 上的中文助手…"}
{"type":"clear_history"}
{"type":"ping"}
```

### llm_daemon → Client

```json
{"type":"token","id":"req-1","text":"你"}
{"type":"done","id":"req-1","usage":{"prefill_ms":120,"generate_ms":800,"tokens":42}}
{"type":"error","id":"req-1","message":"..."}
```

### agent_api → 触屏（预留 · P5c）

WebSocket `ws://127.0.0.1:8765/ws` 推送：`state` · `asr_partial` · `llm_token` · `tts_sentence`

---

## 6. 提示词工程（非微调）

配置文件：`/userdata/agent/config/agent.yaml`

```yaml
system_prompt: |
  你是运行在 youyeetoo R1 上的中文对话助手。回答简洁口语化，单次不超过三句话。
max_new_tokens: 64
max_history_turns: 8
```

- 改 yaml + `set_system_prompt` 或 daemon reload · **不改 rknn 权重**
- InternVL 不支持 v1 热微调；换人设只动 prompt

---

## 7. 实施阶段

| 阶段 | 交付物 | 验收 | 状态 |
|------|--------|------|------|
| **A** | `llm_daemon` + `llm_client` | 10 轮连贯 · TTFT < 500ms · 流式 token | pending |
| **B** | VAD + orchestrator 骨架 | 始终监听 · 2s 说话 → ASR | pending |
| **C** | sherpa online ASR | partial/final 事件 | pending |
| **D** | 分句 TTS 队列 | 首句开播 < 4s E2E | pending |
| **E** | `agent.yaml` + agent_api 占位 | WS 可连 · 状态推送 | pending |
| **S** | VLM spike S1–S3 | 见 §4.1 | parallel |
| **P5b** | `see()` 或统一 `vlm_daemon` | spike 结果定案 | deferred |

顺序：**A → B → C → D → E**；**S 与 A 并行**。

---

## 8. 板端路径

| 资源 | 路径 |
|------|------|
| Agent 根 | `/userdata/agent/` |
| llm_daemon | `/userdata/agent/bin/llm_daemon` |
| 配置 | `/userdata/agent/config/agent.yaml` |
| Orchestrator | `/userdata/agent/orchestrator/` |
| 模型（llm 四件套） | `/userdata/models/InternVL3_5-4B/` |
| 语音硬件 | `source /userdata/voice/scripts/voice_hw_board.sh` |
| 文档（PC） | `youyeetoo3588s/agent/docs/TECH_PLAN.md` |

---

## 9. 决策记录

| ID | 决策 | 选定 | 日期 |
|----|------|------|------|
| D1 | v1 范围 | chat 流式 only · see() → P5b | 2026-08-26 |
| D2 | 触发 | 始终监听 + VAD 端点 | 2026-08-26 |
| D3 | ASR | 3588 CPU · sherpa 本地 online | 2026-08-26 |
| D4 | 编排 | Python asyncio + C++ llm_daemon | 2026-08-26 |
| D5 | 常驻模型 | **InternVL3.5-4B LLM-only 四件套** | 2026-08-26 |
| D6 | 1828 演进 | v1 LLM daemon · 并行 VLM spike · 过则统一 vlm_daemon | 2026-08-26 |
| D7 | 触屏 | agent_api WS 预留 · UI 后排 P5c | 2026-08-26 |

---

## 10. 测试计划

```bash
# Phase A — llm_daemon
/userdata/agent/bin/llm_client --prompt "你好" --stream
/userdata/agent/bin/llm_client --prompt "上一句我说了什么" --stream  # 多轮

# Phase D — 端到端
bash /userdata/agent/scripts/agent_chat.sh

# Spike S1 — 记录 Prefill ms（VM/板端实验脚本待补）
```

---

## 变更日志

| 版本 | 日期 | 说明 |
|------|------|------|
| draft-0 | 2026-08-26 | 初始化骨架 |
| **v1.0** | **2026-08-26** | 锁定模型规格 · 决策 D1–D7 · v1+spike→P5b 路径 |
