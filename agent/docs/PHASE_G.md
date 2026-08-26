# Phase G — 回复长度控制 + TTS Barge-in（阶段 A）

> **状态：** 已实现 · 2026-08-26

## 目标

1. **软约束**：提示词要求小揽按问题复杂度控制长短，全文 ≤100 汉字  
2. **硬约束**：`max_new_tokens` + `max_speak_chars` 双保险  
3. **Barge-in（阶段 A）**：TTS 播放中用户说话 → 立刻停播 → 进入新一轮 ASR

阶段 A **不包含**：LLM 生成中途 cancel（需 `llm_daemon` abort API，见 Phase G-b）。

---

## 配置（`agent/config/agent.yaml`）

```yaml
max_new_tokens: 72          # ~100 汉字生成上限

tts:
  max_sentences: 2          # 每轮最多播 2 句
  max_speak_chars: 100      # 口播汉字硬上限

barge_in:
  enabled: true
  min_speech_sec: 0.35      # 播放期 VAD 段最短时长，过滤回声
```

---

## 长度控制分层

| 层 | 机制 | 文件 |
|----|------|------|
| 软 | `system_prompt` 复杂度 + ≤100 字 | `agent.yaml` |
| 硬（生成） | `max_new_tokens: 72` | `agent.yaml` → `llm_daemon` |
| 硬（口播） | `cap_speak_text()` 按汉字计数截断 | `tts/sentence_split.py` |
| 句数 | `max_sentences` + 只在 `。！？` 分句 | `tts_queue.py` |

---

## Barge-in 架构

```
VAD 线程 ──► vad_queue ──► handle_events（不阻塞）
                              │
                              ├─ speech_start + 正在 TTS → interrupt()
                              └─ audio_segment → turn_queue
                                                    │
                                              turn_worker
                                                    │
                                              ASR → LLM → TTS
```

关键点：

- **`turn_worker`** 独立协程处理整轮，避免 `handle_events` 在 TTS 期间无法收 VAD 事件  
- **`TtsEngine.stop_playback()`** 对 `play_wav.sh` 进程组发 SIGTERM  
- **`TtsQueue.interrupt()`** 清队列 + 停播 + 跳过 post-TTS cooldown  
- **ASR/LLM 期间**仍丢弃新 segment（阶段 A 范围）

---

## 板端验收

```bash
# 推送后重启
bash /userdata/agent/scripts/start_orchestrator.sh
tail -f /userdata/agent/logs/orchestrator.log
```

**长度：**

- 问「你都会做什么事情」→ 口播 ≤100 字，无半句乱读  
- 日志可见 `[llm] reply` 字符数

**Barge-in：**

1. 问一个长问题，等小揽开始说话  
2. 播放中大声说「停」或新问题  
3. 预期：`[barge-in] interrupt TTS playback` → `[tts] interrupted` → 新 ASR 轮

**误触发：**

- 播完 0.8s 内短回声 → `[vad] post-tts cooldown` 或 `[barge-in] segment too short`

---

## 后续 Phase G-b（未做）

- [ ] `llm_daemon` `{"type":"cancel"}` — RKNN3 session abort  
- [ ] 播放期 AEC / 更高 VAD 阈值  
- [ ] InternVL chat template 提升提示词服从率
