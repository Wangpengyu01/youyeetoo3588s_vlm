# MediaMTX + orchestrator 抓图（WHEP / WebRTC）

## 可行性结论

| 路径 | 板端条件 | 典型时延 | 说明 |
|------|----------|----------|------|
| **mediamtx_whep** | mediamtx + `gstreamer1.0-nice` | 首帧：ICE+握手；有缓存 **&lt;100ms** | orchestrator 通过 GStreamer `webrtcbin` 走 WHEP，与 WebUI 同源 WebRTC |
| **mediamtx_rtsp** | mediamtx 常连上游 | 约 **1–2s**/次（冷 gst） | 本机 `rtsp://127.0.0.1:8554/cam`，实现简单，作 WHEP 失败回退 |
| **rtsp 直连摄像头** | 无 mediamtx |  often **2–8s** |  legacy |

WebRTC 在板端抓图**可行**，依赖 **libnice**（`gstreamer1.0-nice`）。板子若无 pip/aiortc，仍可用 **Python gi + webrtcbin**（R1 已具备 `python3-gi`）。

降低 VLM 时延的关键：

1. mediamtx **常连**摄像头（已 `sourceOnDemand: no`）
2. orchestrator 优先读 **`mediamtx_latest.jpg` 缓存**（可选 `mediamtx_whep_daemon.py`）
3. 缓存过期再走 **WHEP 单帧**，失败则 **本机 RTSP**

## Orchestrator 看图（VLM see）

`grab_backend: mediamtx_whep` 时 orchestrator 走 `grab_mediamtx_vlm_pair`：

1. 读 **`mediamtx_latest.jpg` 缓存**（帧守护进程刷新）→ 直接 `see`
2. 否则 WHEP → 本机 mediamtx RTSP

- **「桌面上有什么」** 等物体类问题：**不再**只用旧 scene memory 敷衍，始终对当前帧做 see；**不再**播报「请稍候」填充语（WebUI `vision_start` 已提示）。
- **「我在干什么」** 等活动类：仍可用 scene memory 快答。

## 配置（`agent.yaml`）

```yaml
camera:
  grab_backend: mediamtx_whep   # mediamtx_whep | mediamtx_rtsp | rtsp
  mediamtx:
    path: cam
    rtsp_url: "rtsp://127.0.0.1:8554/cam"
    whep_url: "http://127.0.0.1:8889/cam/whep"
    latest_frame: /userdata/agent/run/mediamtx_latest.jpg
    cache_max_age_sec: 0.8
```

## 板端准备

```bash
# 1) mediamtx（见 p4/scripts/deploy_mediamtx.sh）
# 2) WebRTC ICE 插件
sudo bash /userdata/agent/scripts/install_mediamtx_webrtc_deps.sh
# 3) 冒烟
bash /userdata/agent/scripts/test_whep_grab.sh
```

## 可选：帧缓存守护（进一步压低 see 前抓图）

```bash
nohup python3 /userdata/agent/scripts/mediamtx_whep_daemon.py --interval 0.35 \
  >> /userdata/agent/logs/mediamtx_whep_daemon.log 2>&1 &
```

（当前 daemon 为周期性 WHEP 抓帧；后续可改为长连接单会话。）
