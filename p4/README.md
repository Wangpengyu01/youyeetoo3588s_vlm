# P4 RTSP 1fps 短看图

R1（3588）硬解 RTSP → InternVL3.5-4B（1828）一句话描述。

## 配置

| 项 | 默认值 |
|----|--------|
| R1 静态 IP | 192.168.2.100/24 |
| 网关 | 192.168.2.1 |
| RTSP | rtsp://192.168.2.169:554/stream_2 |
| 流分辨率 | 640×480 |
| VLM 输入 | 448×448 中心裁剪 |

## PC 推送

```powershell
adb push "C:\Users\wwff\Documents\youyeetoo3588s\p4" /userdata/
adb shell "chmod +x /userdata/p4/scripts/*.sh /userdata/p4/scripts/*.py"
```

## 板端

```bash
# 1) 设静态 IP + ping 摄像机
bash /userdata/p4/scripts/net_static.sh

# 2) 探测 RTSP 编码
bash /userdata/p4/scripts/rtsp_probe.sh

# 3) 单次冒烟（取帧 + 描述）
bash /userdata/p4/scripts/p4_test.sh

# 4) 1fps 循环（跑 5 轮）
bash /userdata/p4/scripts/p4_loop.sh 5

# 5) 持续 1fps
bash /userdata/p4/scripts/p4_loop.sh
```

## 环境变量

```bash
export RTSP_URL=rtsp://192.168.2.169:554/stream_2
export STATIC_GW=192.168.2.1
export VLM_PROMPT="用一句话描述当前画面。"
```
