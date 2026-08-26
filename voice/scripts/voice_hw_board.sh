#!/bin/bash
# =============================================================================
# R1 语音硬件配置 · 已冻结 (2026-08-22 v2 · 电平优化)
#   录音：板载 MEMS · MIC_ROUTE=main_board · gain=8
#   播放：SH1.25 J368 GND+L+R · 自动归一化至 target peak
#   验收冻结：2026-08-22 15:00 · 换麦/降噪暂缓
#   勿插 3.5mm TRS 录音
# =============================================================================

export MIC_ROUTE=main_board
export MIC_SOURCE=main
export PLAYBACK_ROUTE=headphone
export PLAYBACK_MONO=stereo
export PLAYBACK_CHANNELS=2

export RECORD_CHANNELS=1
export RECORD_SEC=5
export MIC_CAPTURE_GAIN=8
export MIC_GAIN_LOCK=1
export MIC_ARM_TRIES=10
export MIC_ARM_INTERVAL=0.06

# Playback: auto-normalize quiet TTS/monitor to ~26k peak (max 8x)
export PLAYBACK_NORMALIZE=1
export PLAYBACK_GAIN=4.5
export PLAYBACK_TARGET_PEAK=26000
export PLAYBACK_MAX_GAIN=8.0
export PLAYBACK_RATE=22050
export PLAYBACK_WARMUP_SEC=0.12
export PLAYBACK_LEAD_MS=120
export PLAYBACK_FADE_MS=10
export PLAYBACK_TRIM_MS=60
export PLAYBACK_BUFFER_US=120000
export REPLAY_MONITOR_GAIN=8.0

# ASR: boost quiet captures (peak<2500) before SenseVoice
export ASR_BOOST_MIN_PEAK=8000
export ASR_TARGET_PEAK=16000
export ASR_MAX_GAIN=25.0

export VOICE_RESTORE_MIC=1

echo "[HW] 冻结配置 v2 · 板载麦 + SH1.25 L/R 立体声"
echo "  MIC: ${MIC_ROUTE} gain=${MIC_CAPTURE_GAIN} · PLAY: ${PLAYBACK_RATE}Hz normalize→${PLAYBACK_TARGET_PEAK} ch=${PLAYBACK_CHANNELS}"
