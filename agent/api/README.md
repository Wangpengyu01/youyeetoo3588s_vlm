# agent_api (Phase E)

WebSocket 事件推送，供 HDMI 触屏 UI（P5c）预留。

- URL：`ws://127.0.0.1:8765/ws`（配置见 `config/agent.yaml` → `api:`）
- 实现：stdlib asyncio，无额外 pip 依赖

## 事件类型

| type | 字段 | 说明 |
|------|------|------|
| `hello` | `path` | 连接成功 |
| `state` | `value` | IDLE/LISTEN/ASR/LLM/TTS |
| `asr_partial` | `text` | ASR 中间结果 |
| `asr_final` | `text`, `meta` | ASR 最终结果 |
| `llm_token` | `text` | LLM 流式 token |
| `tts_sentence` | `text` | 待播放分句 |

## 测试

```bash
python3 /userdata/agent/scripts/ws_probe.py
bash /userdata/agent/scripts/phase_e_test.sh
```

PC 经 adb 转发：

```bash
adb forward tcp:8765 tcp:8765
# 然后本地 ws://127.0.0.1:8765/ws
```
