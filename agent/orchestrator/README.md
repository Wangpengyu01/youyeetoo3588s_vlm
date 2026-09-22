# orchestrator

3588 对话状态机（Python asyncio）。

状态：`IDLE → LISTEN → ASR → LLM → TTS → LISTEN`

## Phase D（当前）

- **VAD** + **ASR** + **LLM 流式** + **分句 TTS 队列**
- LLM token 流 → 按句号/逗号分句 → VITS-melo 合成 → `play_wav.sh`

## 对话流畅度

- 默认 `mute_mic_during_tts: false`，播放中仍可说“停”或提出新问题。
- 首个自然短句一生成就进入 TTS；日志会输出 VAD 结束到首 token、首播的分段延迟。
- 每轮语音都有独立 generation，旧轮的延迟合成结果不会混入新回答。
- `mute_mic_during_tts: true` 仅用于定位声学回授，会关闭播放期打断。
- RKNN3 daemon 目前没有取消生成接口；打断会立刻停播并隔离旧输出，但模型后台生成仍会自然收尾。

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
