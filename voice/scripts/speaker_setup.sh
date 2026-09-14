#!/bin/bash
# Playback routing for R1 ES8388.
# PLAYBACK_ROUTE=both      → 3.5mm 孔 + 板载/端子喇叭 双路同时输出 (推荐)
# PLAYBACK_ROUTE=headphone → 仅 3.5mm 孔
# PLAYBACK_ROUTE=onboard   → 仅板载无源喇叭
CARD="${1:-0}"
ROUTE="${PLAYBACK_ROUTE:-both}"

read_val() {
  amixer -c "${CARD}" cget "numid=$1" 2>/dev/null | sed -n 's/^  : values=//p' | head -1
}

# PCM + line-out levels (Output 1/2 max=33 on this codec)
amixer -c "${CARD}" cset numid=21 192,192 >/dev/null
amixer -c "${CARD}" sset 'PCM' 192 >/dev/null 2>&1 || true
amixer -c "${CARD}" cset numid=24 27,27 >/dev/null
amixer -c "${CARD}" cset numid=25 27,27 >/dev/null
amixer -c "${CARD}" cset numid=38 1 >/dev/null   # Left Mixer Playback
amixer -c "${CARD}" cset numid=40 1 >/dev/null   # Right Mixer Playback

case "${ROUTE}" in
  onboard|speaker|board)
    cur_mono=$(read_val 35)
    cur_hp=$(read_val 28)
    cur_spk=$(read_val 29)
    [ "${cur_mono}" != "1" ] && amixer -c "${CARD}" cset numid=35 1 >/dev/null
    [ "${cur_spk}" != "on" ] && amixer -c "${CARD}" cset numid=29 1 >/dev/null
    [ "${cur_hp}" != "off" ] && amixer -c "${CARD}" cset numid=28 0 >/dev/null
    echo "[SPK] 板载喇叭 Mono(Left)" >&2
    ;;
  headphone|hp|jack)
    MONO="${PLAYBACK_MONO:-stereo}"
    case "${MONO}" in
      left)  want_mono=1 ;;
      right) want_mono=2 ;;
      *)     want_mono=0 ;;
    esac
    cur_mono=$(read_val 35)
    cur_hp=$(read_val 28)
    cur_spk=$(read_val 29)
    [ "${cur_mono}" != "${want_mono}" ] && amixer -c "${CARD}" cset numid=35 "${want_mono}" >/dev/null
    [ "${cur_hp}" != "on" ] && amixer -c "${CARD}" cset numid=28 1 >/dev/null
    [ "${cur_spk}" != "off" ] && amixer -c "${CARD}" cset numid=29 0 >/dev/null
    echo "[SPK] 3.5mm Headphone · MonoMux=${MONO}" >&2
    ;;
  both|all|*)
    cur_mono=$(read_val 35)
    cur_hp=$(read_val 28)
    cur_spk=$(read_val 29)
    [ "${cur_mono}" != "0" ] && amixer -c "${CARD}" cset numid=35 0 >/dev/null
    [ "${cur_hp}" != "on" ] && amixer -c "${CARD}" cset numid=28 1 >/dev/null
    [ "${cur_spk}" != "on" ] && amixer -c "${CARD}" cset numid=29 1 >/dev/null
    echo "[SPK] 3.5mm Headphone + 外接/板载喇叭 (双路开启)" >&2
    ;;
esac
