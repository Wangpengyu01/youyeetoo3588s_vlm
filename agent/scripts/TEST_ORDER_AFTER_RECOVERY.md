# 板端恢复 rw 后的推荐测试顺序

**原则：** 一次只开一个 `adb shell` 长命令；看图前避免 `systemctl stop` / `sudo`（易 D-state）；VLM 单次可等 1～3 分钟。

### 卡死 / load 很高时

1. **诊断（应秒回）：** `adb shell "bash /userdata/agent/scripts/adb_board_diag.sh"`
2. **常见原因：**
   - 多个 adb 并行（尤其带 `ip` / `nmcli` / 长 `gst-launch`）→ netlink 阻塞，`ip` 进程进 **D** 态，后续命令像“卡死”。
   - orchestrator **proactive** 每 ~1.5s 抓 RTSP，与手动 `grab_camera_frame` / `run_vlm_once_adb` 抢同一路流。
   - 历史 **`/tmp/rtsp_grab.log` 无写权限** → 旧脚本失败；已改为 `/userdata/agent/logs/rtsp_grab.log`。
3. **软恢复：** `adb shell "bash /userdata/agent/scripts/pause_rtsp_competitors.sh"` 再单独测抓图。
4. **仍 D 态多 / load≫8：** **重启板子**，恢复后**不要**再开第二个 adb 长会话；测 VLM 时可临时关 proactive：`proactive_enabled: false`（`agent.yaml`）。

## 0. 前提（30 秒）

```bash
adb shell "mount | grep userdata"          # 必须 rw
adb shell "systemctl is-active r1-llm-daemon r1-orchestrator r1-p4-eth"
adb shell "python3 /userdata/agent/scripts/llm_client.py --ping"
```

## 1. 纯文字 LLM（不碰 VLM）

```bash
adb shell "python3 /userdata/agent/scripts/llm_client.py --prompt 你好 --max-new 32 --no-stream"
```

通过 → 1828 LLM 路径正常。

## 2. 摄像机网段 + 取帧

```bash
adb shell "bash /userdata/agent/scripts/pause_rtsp_competitors.sh"
adb shell "bash /userdata/agent/scripts/grab_camera_frame.sh /userdata/agent/run/camera_shot.jpg"
adb shell "ls -la /userdata/agent/run/camera_shot.jpg"
```

通过 → RTSP/eth 正常（失败先查 `rtsp.env`、网线）。

## 3. 看图（单次 VLM，手动）

```bash
adb shell "bash /userdata/agent/scripts/cooperative_stop_llm.sh"
adb shell "sudo bash /userdata/p4/scripts/vlm_see.sh /tmp/test.jpg 用一句话描述画面"
adb shell "bash /userdata/agent/scripts/cooperative_start_llm.sh"
```

或一键 spike（含 LLM 基线 + 可选 VLM 180s 上限）：

```bash
adb shell "bash /userdata/p4/scripts/boot_eth_static.sh"
adb shell "bash /userdata/agent/scripts/vlm_spike_s0_board.sh"
```

## 4. 语音 + WebUI

```bash
adb forward tcp:8765 tcp:8765
adb forward tcp:8766 tcp:8766
adb shell "bash /userdata/agent/scripts/open_agent_gui.sh"
```

- 纯文字：WebUI 聊天 / 语音对话  
- 看图：语音带「看看/桌上/画面」或 WebUI「抓拍」

## 5. vlm_daemon（196 编译机，与板端并行）

见 `agent/docs/VLM_DAEMON_DESIGN.md` · Spike S1–S3。
