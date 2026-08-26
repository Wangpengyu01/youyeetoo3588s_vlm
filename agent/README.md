# R1 Agent — 流式对话智能体（P5）

youyeetoo R1（RK3588S）+ RM1828（RK1828）端侧对话智能体。

**当前阶段：** Phase A–E ✅ · Phase F 流式 Paraformer ASR 进行中 · Matcha TTS 已上线

## 与现有代码的关系

| 目录 | 角色 |
|------|------|
| `../voice/` | P3.5 批处理原型（ASR/TTS/LLM shell 链路）· 硬件脚本复用 |
| `../p4/` | RTSP + VLM 看图原型 · `see()` 能力来源 |
| `agent/` | **P5 新架构**：常驻 daemon + 流式编排 |

板端部署目标路径：`/userdata/agent/`（与 `/userdata/voice/`、`/userdata/p4/` 并列）。

## 文档

- [`docs/TECH_PLAN.md`](docs/TECH_PLAN.md) — **v1.0 技术方案**（常驻模型四件套 · IPC · 阶段）
- [`docs/ASR_STREAMING.md`](docs/ASR_STREAMING.md) — **Phase F** streaming Paraformer ASR
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — 架构概览

**常驻模型：** InternVL3.5-4B **LLM-only**（`/userdata/models/InternVL3_5-4B/` llm 四件套 · ~236MB · 1828）

## 目录规划（定型后按 TECH_PLAN 填充）

```
agent/
├── daemon/          # 1828 LLM 常驻进程（C++ · RKNN3 Session）
├── orchestrator/    # 3588 对话编排（Python · 状态机）
├── asr/             # 流式 ASR / VAD 封装
├── tts/             # 分句 TTS / 播放队列
├── vision/          # see() · RTSP 最新帧 · VLM 调度
├── proto/           # IPC 消息定义（JSON Lines / Unix socket）
└── scripts/         # 部署与板端启动
```

## 快速链接

- 路线图 Canvas：`r1-vlm-agent-roadmap.canvas.tsx`
- Phase F Canvas：`asr-streaming-paraformer.canvas.tsx`
- 语音硬件冻结：`../voice/scripts/voice_hw_board.sh`
