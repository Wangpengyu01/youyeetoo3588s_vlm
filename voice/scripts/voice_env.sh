#!/bin/bash
# R1 voice stack: 3588 CPU ASR/TTS, 1828 LLM only
export VOICE_ROOT=/userdata/voice
export SHERPA_ROOT="${VOICE_ROOT}/sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu"
export SHERPA_BIN="${SHERPA_ROOT}/bin"
export SHERPA_LIB="${SHERPA_ROOT}/lib"
export LD_LIBRARY_PATH="${SHERPA_LIB}${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"

export ASR_MODEL="${VOICE_ROOT}/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17"
export TTS_MODEL="${VOICE_ROOT}/vits-melo-tts-zh_en"

export LLM_DIR=/userdata/models/InternVL3_5-4B
export LLM_RKNN="${LLM_DIR}/llm_InternVL3_5-4B.rknn"
export LLM_WEIGHT="${LLM_DIR}/llm_InternVL3_5-4B.weight"
export LLM_TOKENIZER="${LLM_DIR}/InternVL3_5-4B.tokenizer.gguf"
export LLM_EMBED="${LLM_DIR}/InternVL3_5-4B.embed.bin"
export LLM_CORE_MASK=0xff
export LLM_CTX=1024
export LLM_MAX_NEW=64

export RECORD_RATE=16000
export RECORD_CHANNELS="${RECORD_CHANNELS:-1}"
export RECORD_SEC=5

# Mic: main_board=板载 | headset_line2=3.5mm TRRS 耳机麦(常用)
export MIC_SOURCE="${MIC_SOURCE:-main}"
export MIC_ROUTE="${MIC_ROUTE:-main_board}"
export MIC_CAPTURE_GAIN="${MIC_CAPTURE_GAIN:-7}"
export MIC_GAIN_LOCK="${MIC_GAIN_LOCK:-0}"
# headset 有时只有单声道有信号，可试 RECORD_CHANNELS=2 + pick_mono
export RECORD_CHANNELS="${RECORD_CHANNELS:-1}"
export REPLAY_MONITOR_GAIN="${REPLAY_MONITOR_GAIN:-8.0}"
export ASR_BOOST_MIN_PEAK="${ASR_BOOST_MIN_PEAK:-2500}"
export ASR_TARGET_PEAK="${ASR_TARGET_PEAK:-12000}"
export ASR_MAX_GAIN="${ASR_MAX_GAIN:-12.0}"

# Playback: headphone=3.5mm 外接音响 | onboard=板载无源喇叭
export PLAYBACK_ROUTE="${PLAYBACK_ROUTE:-headphone}"
export PLAYBACK_MONO="${PLAYBACK_MONO:-stereo}"
export PLAYBACK_CHANNELS="${PLAYBACK_CHANNELS:-2}"

# Playback: PLAYBACK_NORMALIZE=1 auto-scales to PLAYBACK_TARGET_PEAK (hardware PCM max)
export PLAYBACK_NORMALIZE="${PLAYBACK_NORMALIZE:-1}"
export PLAYBACK_GAIN="${PLAYBACK_GAIN:-2.0}"
export PLAYBACK_TARGET_PEAK="${PLAYBACK_TARGET_PEAK:-14000}"
export PLAYBACK_MAX_GAIN="${PLAYBACK_MAX_GAIN:-4.0}"

# Avoid clipped first syllable after ES8388 route switch
export PLAYBACK_WARMUP_SEC="${PLAYBACK_WARMUP_SEC:-0.12}"
export PLAYBACK_LEAD_MS="${PLAYBACK_LEAD_MS:-120}"
export PLAYBACK_FADE_MS="${PLAYBACK_FADE_MS:-10}"
export PLAYBACK_TRIM_MS="${PLAYBACK_TRIM_MS:-60}"
export PLAYBACK_BUFFER_US="${PLAYBACK_BUFFER_US:-120000}"
