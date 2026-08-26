# Phase F — Streaming Paraformer ASR

> 目标：将 ASR 从 SenseVoice **offline subprocess** 迁移到 **OnlineRecognizer 真流式**，把 `first_play` 从 ~10s 压到 **<5s**。

## 为什么换

| 现状 | 问题 |
|------|------|
| `sherpa-onnx-offline` + SenseVoice int8 | 每轮 subprocess，整段识别 ~7s |
| `asr_partial` | 假流式：对 growing buffer 反复 offline 全量解码 |

## 选型

**模型：** [sherpa-onnx-streaming-paraformer-bilingual-zh-en](https://k2-fsa.github.io/sherpa/onnx/pretrained_models/online-paraformer/paraformer-models.html)

- 离线运行，**不需要联网**
- int8：`encoder.int8.onnx` + `decoder.int8.onnx`（约 226MB）
- 中英 + 多种中文方言
- sherpa-onnx **v1.12.8** C API 已验证（`SherpaOnnxCreateOnlineRecognizer`）

## GitHub 参考项目

| 仓库 | 说明 |
|------|------|
| [k2-fsa/sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) | 官方引擎 · RK3588 · C/Python 示例 |
| [streaming-paraformer-c-api.c](https://github.com/k2-fsa/sherpa-onnx/blob/master/c-api-examples/streaming-paraformer-c-api.c) | C API 解码示例 |
| [streaming-paraformer-asr-microphone.py](https://github.com/k2-fsa/sherpa-onnx/blob/master/python-api-examples/streaming-paraformer-asr-microphone.py) | 麦克风流式 Python |
| [ruzhila/voiceapi](https://github.com/ruzhila/voiceapi) | FastAPI 封装 sherpa ASR+TTS |
| [roomkit voice_local_onnx_vllm.py](https://github.com/roomkit-live/roomkit/blob/main/examples/voice_local_onnx_vllm.py) | VAD+streaming STT+LLM+TTS 全本地 |
| [Unity-Sherpa-ONNX](https://github.com/Ponyu-dev/Unity-Sherpa-ONNX) | VAD + streaming Paraformer 池化参考 |

## 板端路径

```
/userdata/voice/sherpa-onnx-streaming-paraformer-bilingual-zh-en/
├── encoder.int8.onnx
├── decoder.int8.onnx
├── tokens.txt
└── test_wavs/
```

## 安装

```bash
# 板端有网
bash /userdata/agent/scripts/install_streaming_asr.sh

# 或 PC 下载后 adb push（约 1GB tar）
# GitHub:
curl -L -C - -o /tmp/paraformer.tar.bz2 \
  https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-streaming-paraformer-bilingual-zh-en.tar.bz2
# Hugging Face 镜像（GitHub 不稳定时）:
# curl -L -o /tmp/paraformer.tar.bz2 \
#   https://huggingface.co/xumo/onnx_models/resolve/main/sherpa-onnx-streaming-paraformer-bilingual-zh-en.tar.bz2
adb push /tmp/paraformer.tar.bz2 /tmp/
adb shell "tar xf /tmp/paraformer.tar.bz2 -C /userdata/voice"
```

## 配置 (`agent/config/agent.yaml`)

```yaml
asr:
  backend: streaming_paraformer
  model_dir: /userdata/voice/sherpa-onnx-streaming-paraformer-bilingual-zh-en
  encoder: encoder.int8.onnx
  decoder: decoder.int8.onnx
  num_threads: 2
  partial_enabled: true
```

回退 SenseVoice：

```yaml
asr:
  backend: sense_voice
  model_dir: /userdata/voice/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17
```

## 架构

```
speech_start → OnlineStream reset
audio_chunk  → AcceptWaveform → Decode → partial (文本变化时上报)
speech_end   → InputFinished → Decode → final → LLM
```

VAD 仍用 Silero（`asr/sherpa_vad.py`）；OnlineRecognizer `enable_endpoint=0`，端点由 VAD 控制。

## 验收

```bash
bash /userdata/agent/scripts/phase_f_test.sh
# 期望：inject-wav E2E first_play < 5s，日志 [asr] backend=streaming_paraformer
```
