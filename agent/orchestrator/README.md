# orchestrator

3588 对话状态机（Python asyncio）。

状态：`IDLE → LISTEN → ASR → LLM → TTS → LISTEN`

## Phase D（当前）

- **VAD** + **ASR** + **LLM 流式** + **分句 TTS 队列**
- LLM token 流 → 按句号/逗号分句 → VITS-melo 合成 → `play_wav.sh`

## 板端

```bash
bash /userdata/agent/scripts/agent_chat.sh
tail -f /userdata/agent/logs/orchestrator.log

bash /userdata/agent/scripts/phase_d_test.sh
```

## 离线调试

```bash
python3 -m orchestrator.main --inject-wav /path/to/16k.wav --no-partial
python3 -m orchestrator.main --inject-wav /path/to/16k.wav --no-tts
```
