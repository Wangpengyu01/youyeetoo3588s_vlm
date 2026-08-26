#!/bin/bash
# Use HDMI only — disable phantom DSI panel (no physical screen connected).
export DISPLAY=:0
xrandr --output DSI-1 --off 2>/dev/null || true
xrandr --output HDMI-1 --primary --mode 1920x1080 --pos 0x0 2>/dev/null || \
  xrandr --output HDMI-1 --primary --pos 0x0 2>/dev/null || true
