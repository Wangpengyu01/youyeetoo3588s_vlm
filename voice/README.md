# R1 语音对话（3588 ASR/TTS + 1828 LLM）

## 架构

- **RK3588 CPU**：麦克风录音、SenseVoice ASR、VITS TTS 播放
- **RM1828**：InternVL3.5-4B 纯文本 LLM（`llm_*.rknn`，无 vision）

## 板端路径

```
/userdata/voice/
├── sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu/   # sherpa 二进制
├── sherpa-onnx-sense-voice-...-int8-2024-07-17/    # ASR 模型
├── vits-melo-tts-zh_en/                            # TTS 模型
└── scripts/
    ├── voice_env.sh
    ├── asr.sh           # 录音 + 识别
    ├── tts.sh           # 文字 → 喇叭
    ├── llm_ask.py       # 文字 → 1828 LLM
    ├── test_llm_tts.sh  # 一键测 LLM+TTS（不需麦克风）
    └── voice_chat.sh    # 完整语音对话循环
```

## 使用方法（SSH/adb shell 到板子）

```bash
# 1. 仅测 LLM + TTS（固定文字，约 60s 首次含模型加载）
bash /userdata/voice/scripts/test_llm_tts.sh "你好，请用一句话介绍你自己。"

# 2. 完整语音对话（需接麦克风/喇叭）
bash /userdata/voice/scripts/voice_chat.sh
```

## PC 端解压（用 Bandizip，不要用 tar）

以下 **已完成**，无需重复解压：

| 文件 | 解压到 |
|------|--------|
| `sherpa-onnx-aarch64-cpu.tar.bz2` | `voice/sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu/` |
| `sensevoice-int8.tar.bz2` | `voice/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17/` |
| `vits-melo-tts-zh_en.tar.bz2` | `voice/vits-melo-tts-zh_en/` |

**可选**（用于后续编译正式 `llm_chat` 替代 patch 方案）：

从 `RK1820_1828_RELEASE_V1.0.5B10.tar.gz` 仅解压：

```
rel_182x/rknn/rknn3-runtime/examples/rknn3_session_test_demo/
```

## 已知限制

1. **首次 LLM 调用 ~25s**（RM1828 加载模型）；后续同会话会快很多
2. **TTS RTF ~1.3–2.6**（3588 CPU VITS，短句可接受）
3. `llm_ask.py` 临时 patch 了 `rknn3_session_test` 二进制内 prompt（≤15 汉字）；SDK 源码编译后可去掉此 hack
4. ASR 录音默认 5s，可在 `voice_env.sh` 改 `RECORD_SEC`

## 单独测试

```bash
source /userdata/voice/scripts/voice_env.sh
bash /userdata/voice/scripts/asr.sh          # 录音 5s 并识别
bash /userdata/voice/scripts/tts.sh "测试语音合成"
python3 /userdata/voice/scripts/llm_ask.py "今天天气怎么样？"
```
