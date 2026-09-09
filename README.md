# 小揽 R1：RK3588S 离线语音助手

> **本地听、当地想、立刻说。**
>
> RK3588S 负责听觉、语音合成和对话编排；RM1828 常驻大语言模型。整个语音对话链路不依赖云端接口，适合做可落地的桌面语音助手原型。

本仓库是基于上游 [`xiaolaohu123wf/youyeetoo3588s_vlm`](https://github.com/xiaolaohu123wf/youyeetoo3588s_vlm) 的同源开发分支，保留原项目内容，并集中收录“小揽”离线语音对话的改进。

## 它能做什么

- 使用板载麦克风持续监听，说完即可对话
- VAD 自动判断说话起止，流式识别中文语音
- RM1828 上常驻 **InternVL3.5-4B（LLM-only）**，避免每轮加载模型
- LLM 逐 token 输出；TTS 按句开始合成和播放，不必等整段回答完成
- 支持“停 / 停止 / 别说了”等打断指令
- HDMI 控制面板可通过 WebSocket 获得识别、生成和播放状态

## 当前架构

```text
板载麦克风
   │
   ├─ VAD（语音活动检测）
   └─ Streaming Paraformer ASR（流式中文识别）
                 │
        asyncio 对话编排器（RK3588S）
                 │ Unix Socket，逐 token 返回
                 ▼
 RM1828：llm_daemon + InternVL3.5-4B LLM-only
                 │
    分句缓冲 → Matcha 中文 TTS → 扬声器
```

## 本分支完成的关键优化

| 方向 | 处理方式 |
| --- | --- |
| 首次回答更快 | 将 LLM 做成常驻 daemon，Socket 流式返回 token；语音合成随句播放。 |
| 复杂问题不截断 | 单轮最大生成长度提升到 768 token，生成到上限时协议明确标为 `length`，避免错误续写、重复回答。 |
| 回答更连贯 | 对话请求默认只携带当前问题，规避小上下文模型被无关历史锚定。 |
| 识别不丢开头 | 最终识别阶段会从完整 VAD 片段重新送入识别器，修复流式阶段与预录音拼接时遗漏句首的问题。 |
| 随时可打断 | 收到停止意图立即中断 LLM 和 TTS，不再等待本轮播完。 |
| 板端音频可用 | 固化了扬声器、板载麦克风、采集增益及回声期间的采集策略。 |

## 已在板端验证的表现

在当前 RK3588S + RM1828 的实机环境中，LLM 首 token 约 **244 ms**；一次约 520 字的复杂回答完整生成约 **4.14 s**。实际听感会比“整段生成后再播放”更快，因为第一句合成完就会开始出声。

## 硬件与模型

- **RK3588S**：VAD、Streaming Paraformer ASR、Matcha TTS、编排服务与控制面板
- **RM1828**：InternVL3.5-4B LLM-only 的 RKNN 常驻推理
- **音频**：板载麦克风与扬声器
- **模型文件**：不提交到 Git 仓库；板端默认从 `/userdata/models/InternVL3_5-4B/` 读取 LLM 四件套

## 目录说明

| 路径 | 作用 |
| --- | --- |
| `agent/orchestrator/` | 异步对话编排、流式输出、打断与 WebSocket 状态 |
| `agent/asr/` | 流式 Paraformer / SenseVoice 识别后端 |
| `agent/tts/` | Matcha 中文语音合成与分句播放 |
| `agent/daemon/` | RM1828 的 C++ LLM 常驻服务 |
| `agent/config/agent.yaml` | 语音、生成长度与硬件策略配置 |
| `agent/tests/` | 流式对话、ASR 最终识别和配置回归测试 |
| `voice/scripts/` | 扬声器、麦克风与板端音频初始化脚本 |
| `docs/`、`agent/docs/` | 架构与部署资料 |

## 板端运行

部署模型与程序后，服务通常以 `r1-llm-daemon` 和 `r1-orchestrator` 运行。可在板端检查状态：

```bash
systemctl status r1-llm-daemon r1-orchestrator
journalctl -u r1-orchestrator -f
```

本机测试入口在 `agent/tests/`。模型文件、板端运行库和声学环境会影响最终时延与识别率，部署前应按实际硬件路径调整 `agent/config/agent.yaml`。

## 当前边界

- 当前主链路是 **LLM-only 语音对话**；视觉模型与统一 VLM daemon 仍是后续工作。
- 模型的固定上下文窗口约为 1024 token，不能宣称“无限上下文”；较长回答已通过 768 token 的单轮预算保证足够完整。
- 免按键打断在近距离扬声器和麦克风环境中仍会受物理回声影响；若要做真正的全双工唤醒，需要进一步接入 AEC。

## 致谢与来源

原始工程来自 [xiaolaohu123wf/youyeetoo3588s_vlm](https://github.com/xiaolaohu123wf/youyeetoo3588s_vlm)。本仓库在其基础上增加和整合了本地语音对话、流式编排、音频路由、打断控制、长回答与 ASR 最终识别修复等工作。详见提交历史。
