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
cd p4
.\push_p4.ps1
```

（脚本会把 `.sh` / `.env` 转为 LF，并推到 `/userdata/p4/`。）

## 板端

```bash
# 0) 一次性：NM 持久静态 IP（推荐，重启后仍有效）
sudo bash /userdata/p4/scripts/install_eth_static_persistent.sh
sudo cp /userdata/agent/systemd/r1-p4-eth.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now r1-p4-eth.service

# 可选：复制 config/rtsp.env.example → config/rtsp.env 并填入账号密码

# 1) 临时改 IP（旧方式，会改 NM_CONN 连接）
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
