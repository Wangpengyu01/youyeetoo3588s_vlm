# orchestrator

3588 对话状态机（Python asyncio）。

状态：`IDLE → LISTEN → ASR → LLM → TTS → LISTEN`

## Phase C（当前）

- **VAD**：sherpa Silero + 常开 mic
- **ASR**：SenseVoice · `asr_partial` / `asr_final` 事件
- **LLM**：识别完成后自动调 `llm_daemon`
- **TTS**：stub（Phase D）

## 板端

```bash
bash /userdata/agent/scripts/start_orchestrator.sh
tail -f /userdata/agent/logs/orchestrator.log

bash /userdata/agent/scripts/phase_c_test.sh
```

实时模式下对着板载麦说话，日志可见 partial（最多 3 次/句）和 final。

## 离线调试

```bash
python3 -m orchestrator.main --inject-wav /path/to/16k.wav --no-partial
```
