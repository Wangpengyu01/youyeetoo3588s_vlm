# 小揽 · RK3588 边缘多模态智能终端 全栈部署与交付总结手册
**Xiao Lan Multimodal Embodied AI — Integrated Deployment & VLM Delivery Manual**
*版本: v2.7.8 正式交付版 | 适用平台: Rockchip RK3588 + RM1828 NPU 加速卡*

---

## 目录
1. [系统架构与资源调度机制](#一-系统架构与资源调度机制)
2. [两种部署安装模式完全指南](#二-两种部署安装模式完全指南)
   - [模式一：USB ADB 离线部署模式（无网络/内网推荐）](#模式一usb-adb-离线部署模式无网络内网推荐)
   - [模式二：局域网在线 Git 部署模式](#模式二局域网在线-git-部署模式)
3. [看图说话（InternVL + TTS）整链打通方案](#三-看图说话internvl--tts整链打通方案)
   - [1828 显存独占机制与调度规则](#1-1828-显存独占机制与调度规则)
   - [缺少 rknn_InternVLM_demo 根因与补齐](#2-缺少-rknn_internvlm_demo-根因与补齐)
   - [分步验证与全链路冒烟测试](#3-分步验证与全链路冒烟测试)
4. [RTSP 视频流配置与 Web UI 控制台](#四-rtsp-视频流配置与-web-ui-控制台)
5. [4 项核心功能验收清单](#五-4-项核心功能验收清单)
6. [常见问题排查速查表 (FAQ)](#六-常见问题排查速查表-faq)
7. [版本发布与交付信息](#七-版本发布与交付信息)

---

## 一、 系统架构与资源调度机制

小揽系统由 **RK3588 边缘计算主板** 与 **RM1828 PCIe 独立 NPU 加速卡** 协同构成：

```
                              ┌────────────────────────────────────────────────────────┐
                              │                   小揽 边缘端多模态中枢                 │
                              └────────────────────────────────────────────────────────┘
                                               │                     │
                     ┌─────────────────────────┴────────┐   ┌────────┴─────────────────────────┐
                     ▼                                  ▼   ▼                                  ▼
         【RK3588 板载协同中枢】                    【RM1828 PCIe 算力卡】             【双向 WebSocket API】
         • Silero-VAD 实时音频流断句                 • 显存容量: 5120 MB                • 端口: 8765 (/ws)
         • SenseVoice 流式语音识别 (~120ms)         • 语音 LLM 会话 (llm_daemon)       • 实时事件全量广播
         • GStreamer MPP 硬件 RTSP 解码              • 视觉 VLM 会话 (InternVL3.5-4B)   • 远程控制/外部文本注入
         • Matcha-TTS / Sherpa 语音合成             • 【注: LLM 与 VLM 在 1828 互斥】   ────────────────────────
         • Web UI 控制台服务 (端口: 8766)                                              【现代化 Web UI 控制台】
         • 零等待视觉场景工作记忆库                                                    • 实时 RTSP 画面监视 (MPP)
                                                                                        • 1秒零等待场景回答库
                                                                                        • Canvas 状态律动音频波形
```

---

## 二、 两种部署安装模式完全指南

### 模式一：USB ADB 离线部署模式（无网络/内网推荐）

当开发板处于内网隔离环境、尚未接入 Wi-Fi/以太网，或开发者习惯使用电脑通过 Type-C 数据线直连调试时，使用此模式。

#### 1. 核心原理
- **纯 USB 通信**：无需板卡 IP 地址，无需局域网网络。
- **端口映射穿透 (`adb forward`)**：将板卡内的 Web 控制台端口（`8766`）和 WebSocket 端口（`8765`）映射至电脑本机 `localhost`，在电脑浏览器打开 `http://127.0.0.1:8766` 即可操控板卡。
- **全量资产自动推送**：同步推入 `agent`（核心中枢）、`rknn_InternVLM_demo`（看图模型可执行程序）及 `p4`（RTSP 看图说话脚本）。

#### 2. Windows PC 一键全自动脚本
项目根目录内置了 [`deploy_via_adb.bat`](file:///g:/wend/3588/deploy_via_adb.bat)，双击运行即可全自动完成：
```bat
:: 双击 deploy_via_adb.bat 自动执行：
:: 1. 检测板卡连接 (adb devices)
:: 2. 推送 agent 源码至 /userdata/agent
:: 3. 推送 InternVL 程序至 /userdata/rknn_InternVLM_demo
:: 4. 推送 P4 脚本至 /userdata/p4
:: 5. 赋予所有脚本可执行权限 (chmod +x)
:: 6. 执行端口映射 (adb forward tcp:8766 & tcp:8765)
:: 7. 按提示按 [1] 直接拉起服务并弹出电脑浏览器控制台
```

#### 3. Linux / Mac PC 一键脚本
```bash
bash agent/scripts/deploy_to_board.sh
```

#### 4. 手动标准 ADB 命令行清单（备查）
```powershell
# 1. 检查板卡是否连接
adb devices

# 2. 推送 agent 核心系统并授权
adb shell "mkdir -p /userdata/agent"
adb push agent\. /userdata/agent/
adb shell "chmod +x /userdata/agent/scripts/*.sh"

# 3. 推送 InternVL 看图程序与 P4 脚本
adb shell "mkdir -p /userdata/rknn_InternVLM_demo /userdata/p4"
adb push rknn_InternVLM_demo\. /userdata/rknn_InternVLM_demo/
adb push p4\. /userdata/p4/
adb shell "chmod +x /userdata/rknn_InternVLM_demo/rknn_internvl3_demo /userdata/p4/scripts/*.sh /userdata/p4/scripts/*.py"

# 4. 建立 USB 端口穿透
adb forward tcp:8766 tcp:8766
adb forward tcp:8765 tcp:8765

# 5. 启动小揽全套服务
adb shell "bash /userdata/agent/scripts/quickstart_all.sh"

# 6. 查看运行日志
adb shell "tail -f /userdata/agent/logs/orchestrator.log"
```

---

### 模式二：局域网在线 Git 部署模式

当板卡已接入局域网且具备公网访问能力时：

```bash
# 1. 在板端创建并进入部署目录
mkdir -p /userdata
cd /userdata

# 2. 克隆正式发布的 v2.7.8 稳定版本
git clone -b v2.7.8 https://github.com/Wangpengyu01/youyeetoo3588s_vlm.git agent
cd /userdata/agent

# 3. 补齐板端根目录组件（若从全量仓库运行）
cp -r rknn_InternVLM_demo /userdata/ 2>/dev/null || true
cp -r p4 /userdata/ 2>/dev/null || true
chmod +x /userdata/rknn_InternVLM_demo/rknn_internvl3_demo /userdata/p4/scripts/*.sh /userdata/agent/scripts/*.sh

# 4. 一键启动所有服务 (端侧 LLM + 智能体 + Web UI)
bash /userdata/agent/scripts/quickstart_all.sh

# 查看所有组件实时状态
bash /userdata/agent/scripts/quickstart_all.sh status

# 停止所有服务
bash /userdata/agent/scripts/quickstart_all.sh stop
```

---

## 三、 看图说话（InternVL + TTS）整链打通方案

### 1. 1828 显存独占机制与调度规则
- **单会话互斥原理**：RM1828 PCIe 算力卡驱动在同一时刻**只能维系一个活跃的 RKNN3 模型会话**。
- **调度冲突**：
  - 语音对话时，后台运行的 `llm_daemon` 独占 1828 会话。
  - 若此时直接调用 `rknn_internvl3_demo`，驱动会抛出 `MODEL_SETUP fail`（显存/会话已被占用）。
- **调度规则**：在执行看图说话前，**必须先停止语音 LLM 进程**（释放 1828 显存）；使用完毕后再启动。

### 2. 缺少 `rknn_InternVLM_demo` 根因与补齐
- **根因**：可执行程序 `rknn_internvl3_demo` 位于仓库根目录 `rknn_InternVLM_demo/` 下。若部署时仅推送了 `agent/` 目录，板卡 `/userdata/` 下便会缺少该工具，导致 `vlm_see.sh` 找不到执行程序。
- **补齐命令**：
  ```powershell
  # 在 PC 仓库根目录执行
  adb push rknn_InternVLM_demo /userdata/
  adb shell "chmod +x /userdata/rknn_InternVLM_demo/rknn_internvl3_demo"
  ```

### 3. 分步验证与全链路冒烟测试

#### 步骤 1：确认 1828 显存释放
```bash
adb shell rknn-smi info
# 观察 Memory 占用，确认已下降至接近 0 MB（低于 1500 MB 即可）
```

#### 步骤 2：单步验证 InternVL 看图推理
```bash
adb shell
cd /userdata/rknn_InternVLM_demo
export LD_LIBRARY_PATH=.:/usr/lib:/usr/local/lib

./rknn_internvl3_demo \
  /userdata/models/InternVL3_5-4B/vision_InternVL3_5-4B.rknn \
  /userdata/models/InternVL3_5-4B/vision_InternVL3_5-4B.weight \
  /userdata/models/InternVL3_5-4B/llm_InternVL3_5-4B.rknn \
  /userdata/models/InternVL3_5-4B/llm_InternVL3_5-4B.weight \
  /userdata/models/InternVL3_5-4B/InternVL3_5-4B.tokenizer.gguf \
  /userdata/models/InternVL3_5-4B/InternVL3_5-4B.embed.bin \
  0xff 0xff model/demo.jpg "用一句话描述这张图片。"
```
> **预期指标**：Vision latency ≈ 190ms，Prefill 速度 ≈ 625 tok/s，终端打印出对图片的中文描述。

#### 步骤 3：单步验证 TTS 语音播报（3588 CPU）
```bash
adb shell bash /userdata/voice/scripts/tts.sh "测试语音播报正常，准备执行看图说话。"
```
> **预期效果**：J368 喇叭/耳机清晰播报出该语音。

#### 步骤 4：一键执行【取帧 -> InternVL推理 -> TTS播报】完整流水线
```bash
adb shell bash /userdata/p4/scripts/p4_test.sh
```
> **链路流转过程**：
> 1. `net_static.sh`: 确保网络通畅并能通信摄像机；
> 2. `p4_check_1828.sh`: 校验 1828 处于空闲状态；
> 3. `rtsp_grab_once.sh`: 通过 RTSP 硬件抓取一帧并裁剪为 448×448；
> 4. `vlm_see.sh`: 调用 InternVL 获得画面描述；
> 5. `p4_tts.sh`: 自动联动 TTS，将识别出的画面文字朗读出来！

---

## 四、 RTSP 视频流配置与 Web UI 控制台

### 1. RTSP 视频流配置
- **配置文件修改**：在 `/userdata/agent/config/agent.yaml` 中配置：
  ```yaml
  camera:
    enabled: true
    url: "rtsp://192.168.1.100:554/live"  # 填入摄像机 RTSP 地址
    rtsp_transport: "tcp"                # 优先推荐 tcp，防花屏丢包
    timeout: 2.5
    size: 448
  ```
- **Web 控制台动态切换（免重启）**：直接在 Web 界面左侧视频窗口下的输入框粘贴新的 RTSP URL，点击【切换流】按键立即生效。

### 2. Web UI 控制台访问
- **局域网外部设备访问**：`http://<RK3588板卡IP>:8766`
- **板载 HDMI 屏幕访问**：`http://127.0.0.1:8766`
- **USB ADB 转发访问**：在 PC 浏览器打开 `http://127.0.0.1:8766`

### 3. 控制台界面功能分区说明
- **左上 · 实时视频监控窗口**：MPP 硬件解码实时帧回传，展示动态感知指数 HUD（检测手部/人体动作）。
- **左下 · 视觉场景工作记忆**：实时展示当前场景理解内容、主人工作专注状态（如“专注编程中”）、目标标签（如“💻 笔记本电脑”、“⌨️ 键盘”、“🥛 水杯”）。
- **右上 · 音频律动 Canvas 波形**：多模态声学状态自适应变化（空闲、聆听、识别、思考、播报），支持“🛑 打断”按键。
- **右中 · 实时对话流**：流式打字机回复，提供一键快捷指令（无需麦克风也能点击测试）。
- **底部 · 硬件延时遥测栏**：透明化展示 ASR 耗时 (~120ms)、TTFT 首字延迟 (~180ms)、TTS 首包延迟 (~220ms)、端到端总延时 (~510ms)。

---

## 五、 4 项核心功能验收清单

| 验收项目 | 操作步骤 | 验收标准 |
| :--- | :--- | :--- |
| **1. 桌面物品 1 秒极速问答** | 对麦克风提问“*桌面上有什么？*”或点击 Web 控制台快捷按键【🔍 桌面上有什么？】 | 小揽在 **1 秒内** 立即以清脆语音回答桌面的核心物品（如：“*主人，桌上有一台笔记本电脑、机械键盘和水杯*”），Web 场景记忆卡片同步高亮。 |
| **2. 主人行为状态感知** | 坐在电脑前打字，提问“*小揽，看我正在干什么？*”或点击快捷按键【👀 我在干什么？】 | 小揽立即精准回答：“*主人，我看到您正在电脑前编写和调试代码，面前放有键盘、鼠标和水杯。*” |
| **3. 动态热切换 RTSP 视频流** | 在 Web 控制台输入框输入新的 RTSP 流地址并点击【切换流】 | 状态指示灯变为绿色，视频窗口即刻载入新视频流画面，无需重启服务。 |
| **4. 实时语音打断 (Barge-in)** | 在小揽播报过程中直接说“*停*”或在 Web 控制台点击右上角【🛑 打断】 | 语音播报在 100ms 内截断静音，状态立即切回聆听，随时接收下一条指令。 |

---

## 六、 常见问题排查速查表 (FAQ)

### 1. 运行看图提示缺少 `/userdata/rknn_InternVLM_demo`？
- **原因**：板端缺少 InternVL 二进制程序目录。
- **解决**：在 PC 仓库根目录执行：
  ```powershell
  adb push rknn_InternVLM_demo /userdata/
  adb shell "chmod +x /userdata/rknn_InternVLM_demo/rknn_internvl3_demo"
  ```

### 2. 1828 报错 `MODEL_SETUP fail` 或显存已满？
- **原因**：语音 `llm_daemon` 或上一轮崩溃的 VLM 进程仍占有 1828 显存会话。
- **解决**：
  ```bash
  # 停止语音大模型
  pkill -f llm_daemon
  # 查看显存是否归零
  rknn-smi info
  # 若仍未释放，执行冷重启：
  adb reboot
  ```

### 3. 视频监视窗口显示“等待视频流或摄像头抓帧…”？
- **原因**：RTSP 地址不可达或网络中断。
- **解决**：
  - 在 PC 上使用 VLC 播放器测试该 RTSP URL 是否能拉流；
  - 检查板卡是否具备解码库：`which gst-launch-1.0 ffmpeg`；
  - 点击 Web 控制台上的【📷 拍照识别】按钮尝试单次强制抓取。

### 4. 电脑浏览器打不开 `http://<板卡IP>:8766`？
- **解决**：
  - 如果走网络：检查板卡防火墙：`sudo ufw allow 8765/tcp && sudo ufw allow 8766/tcp`；
  - 如果走 USB 数据线：确认执行了端口映射：`adb forward tcp:8766 tcp:8766`，电脑直接访问 `http://127.0.0.1:8766`。

### 5. 播报没有声音？
- **解决**：
  - 运行 `aplay -l` 确认声卡设备；
  - 运行 `alsamixer` 确认耳机/喇叭通道没有被 Mute (静音)。

---

## 七、 版本发布与交付信息

- **当前正式交付版本**：`v2.7.8`
- **GitHub Release 页面**：[https://github.com/Wangpengyu01/youyeetoo3588s_vlm/releases/tag/v2.7.8](https://github.com/Wangpengyu01/youyeetoo3588s_vlm/releases/tag/v2.7.8)
- **代码分支**：`wpy/r1-voice-all-improvements`
- **主仓地址**：`https://github.com/Wangpengyu01/youyeetoo3588s_vlm.git`
- **自动化测试覆盖率**：`36 / 36 PASSED (OK)`
