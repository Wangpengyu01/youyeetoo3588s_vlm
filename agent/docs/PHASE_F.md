# Phase F — Streaming Paraformer ASR

> 目标：将 ASR 从 SenseVoice **offline subprocess** 迁移到 **OnlineRecognizer 真流式**，把 `first_play` 从 ~10s 压到 **<5s**。

详见 [ASR_STREAMING.md](./ASR_STREAMING.md)。

## 状态

| 项 | 状态 |
|----|------|
| 调研 + Canvas | 进行中 |
| `sherpa_streaming_asr.py` | 进行中 |
| 板端模型 | 待下载 (~1GB tar) |
| `phase_f_test.sh` | 待添加 |

## 实施阶段表（追加）

| 阶段 | 交付物 | 验收 |
|------|--------|------|
| **F** | Streaming Paraformer ASR | inject-wav · first_play < 5s · 真 partial |
