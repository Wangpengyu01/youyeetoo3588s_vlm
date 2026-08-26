#!/bin/bash
# ES8388/ES8323 capture routing for R1.
CARD="${1:-0}"
MIC_SOURCE="${MIC_SOURCE:-main}"
MIC_ROUTE="${MIC_ROUTE:-main_board}"

echo "[MIC] 输入: ${MIC_SOURCE} 路由: ${MIC_ROUTE} (card ${CARD})..."

amixer -c "${CARD}" cset numid=13 0 >/dev/null   # ALC NG off
amixer -c "${CARD}" cset numid=12 0 >/dev/null   # Constant PGA (not mute ADC)
amixer -c "${CARD}" cset numid=16 0 >/dev/null   # Capture Mute off
amixer -c "${CARD}" cset numid=6 0 >/dev/null    # ALC Capture Function off (fixed gain)
amixer -c "${CARD}" cset numid=34 0 >/dev/null   # Differential Mux Line 1
amixer -c "${CARD}" sset 'Capture Digital' 192 >/dev/null 2>&1 || true

GAIN="${MIC_CAPTURE_GAIN:-5}"
amixer -c "${CARD}" cset numid=17 "${GAIN}" >/dev/null
amixer -c "${CARD}" cset numid=18 "${GAIN}" >/dev/null

case "${MIC_ROUTE}" in
  headset_line2)
    amixer -c "${CARD}" cset numid=36 1 >/dev/null
    amixer -c "${CARD}" cset numid=37 1 >/dev/null
    amixer -c "${CARD}" cset numid=32 1 >/dev/null
    amixer -c "${CARD}" cset numid=33 1 >/dev/null
    amixer -c "${CARD}" cset numid=30 0 >/dev/null
    amixer -c "${CARD}" cset numid=31 1 >/dev/null
    ;;
  headset_line1)
    amixer -c "${CARD}" cset numid=36 0 >/dev/null
    amixer -c "${CARD}" cset numid=37 0 >/dev/null
    amixer -c "${CARD}" cset numid=32 0 >/dev/null
    amixer -c "${CARD}" cset numid=33 0 >/dev/null
    amixer -c "${CARD}" cset numid=30 0 >/dev/null
    amixer -c "${CARD}" cset numid=31 1 >/dev/null
    ;;
  main_board|main)
    amixer -c "${CARD}" cset numid=36 3 >/dev/null
    amixer -c "${CARD}" cset numid=37 3 >/dev/null
    amixer -c "${CARD}" cset numid=32 0 >/dev/null
    amixer -c "${CARD}" cset numid=33 0 >/dev/null
    amixer -c "${CARD}" cset numid=30 1 >/dev/null
    amixer -c "${CARD}" cset numid=31 0 >/dev/null
    # Headphone 播放路由会把 Headset Mic 拉回 on，板载麦必须再关一次
    amixer -c "${CARD}" cset numid=31 0 >/dev/null
    ;;
  headset_miclr|*)
    # 外接咪头常用：Headset Mic + MicL/MicR 通路
    amixer -c "${CARD}" cset numid=36 3 >/dev/null
    amixer -c "${CARD}" cset numid=37 3 >/dev/null
    amixer -c "${CARD}" cset numid=32 0 >/dev/null
    amixer -c "${CARD}" cset numid=33 0 >/dev/null
    amixer -c "${CARD}" cset numid=30 0 >/dev/null
    amixer -c "${CARD}" cset numid=31 1 >/dev/null
    ;;
esac

read_mixer() {
  amixer -c "${CARD}" cget "numid=$1" 2>/dev/null | sed -n 's/^  : values=//p' | head -1
}

LMUX=$(read_mixer 36)
MAIN=$(read_mixer 30)
HSET=$(read_mixer 31)
HP=$(read_mixer 26)
echo "[MIC] Gain=${GAIN} route=${MIC_ROUTE} HPjack=${HP:-?} LineMux=${LMUX:-?} MainMic=${MAIN:-?} HeadsetMic=${HSET:-?}"
