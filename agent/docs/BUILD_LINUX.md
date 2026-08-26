# llm_daemon 交叉编译（Linux VM）

在 **gp@192.168.100.196** R1 SDK Docker 内编译，产物 adb push 到板端。

## 1. 前提

- VM 已有 RKNN3 SDK 1.0.5b10 与 `rknn3_session_test_demo` 完整源码树（含 `Tokenizer.h`、`Makefile`）
- 板端已验收：`rknn3_session_test` LLM-only 可跑（P3）

典型 SDK 示例路径（按你 VM 实际调整）：

```text
~/r1-sdk/rknn/rknn3-runtime/examples/rknn3_session_test_demo/
├── Makefile
├── src/rknn3_session_test.cpp
├── include/Tokenizer.h
└── ...
```

## 2. 拷贝 daemon 源码

在 **PC** 仓库已含 `agent/daemon/llm_daemon.cpp`。传到 VM：

```bash
# PC → VM（示例）
scp agent/daemon/llm_daemon.cpp gp@192.168.100.196:~/r1-sdk/rknn/rknn3-runtime/examples/rknn3_session_test_demo/src/
```

或在 VM 内 `git clone` 你的 GitHub 仓库后复制：

```bash
cp ~/youyeetoo3588s_vlm/agent/daemon/llm_daemon.cpp \
   ~/r1-sdk/rknn/rknn3-runtime/examples/rknn3_session_test_demo/src/
```

## 3. 修改 Makefile（一次性）

在 `rknn3_session_test_demo/Makefile` 增加第二个目标，**或**单独一行编译：

```makefile
# 追加目标示例
llm_daemon: src/llm_daemon.cpp src/Tokenizer.cpp
	$(CXX) $(CXXFLAGS) $(INCLUDES) -o llm_daemon $^ $(LDFLAGS) $(LIBS)
```

若不想改 Makefile，Docker 内手动编译（路径按 SDK 调整）：

```bash
cd ~/r1-sdk/rknn/rknn3-runtime/examples/rknn3_session_test_demo

export RKNN3_API_PATH=../../rknn3-api
export CXX=aarch64-linux-gnu-g++

$aarch64-linux-gnu-g++ -O2 -std=c++17 \
  -I./include -I${RKNN3_API_PATH}/include \
  -o llm_daemon \
  src/llm_daemon.cpp src/Tokenizer.cpp \
  -L${RKNN3_API_PATH}/lib/aarch64 -lrknn3_api \
  -lpthread -ldl
```

> 若 `Tokenizer.cpp` 路径不同，以 SDK demo 目录现有 `Makefile` 为准，**与编 rknn3_session_test 相同 flags**。

## 4. 编译

```bash
# Docker 内
make llm_daemon
# 或 make 后手动 g++（见上）

file llm_daemon
# 期望: ELF 64-bit LSB executable, ARM aarch64
```

## 5. 推到板端

```bash
# VM → 板（adb 连 PC 时可在 PC 上 pull 再 push）
adb push llm_daemon /userdata/agent/bin/llm_daemon
adb shell chmod +x /userdata/agent/bin/llm_daemon
```

PC 端也可：

```powershell
adb push agent\bin\llm_daemon /userdata/agent/bin/llm_daemon
```

## 6. 板端验收

```bash
# 推送脚本（PC）
powershell -File agent/scripts/push_agent.ps1

adb shell
bash /userdata/agent/scripts/start_llm_daemon.sh
bash /userdata/agent/scripts/phase_a_test.sh
```

单客户端测试：

```bash
python3 /userdata/agent/scripts/llm_client.py --ping
python3 /userdata/agent/scripts/llm_client.py --prompt "你好，请用一句话介绍你自己。"
```

## 7. 通过判据（Phase A）

| 项 | 判据 |
|----|------|
| 启动 | `/tmp/r1-llm.sock` 存在 · `rknn-smi` 显存 ~236MB 级 |
| ping | `{"type":"pong"}` |
| 单轮 | 流式 token · `done.prefill_ms` < 500ms（daemon 已热） |
| 多轮 | 第二问能引用上下文 |
| 对比 | 同 prompt · 比 `llm_ask.py` 每轮快 **一个数量级** |

## 8. 故障

| 现象 | 处理 |
|------|------|
| `No RK182X devices` | 冷启 `adb reboot` · 勿 manual restart rknn3 |
| init failed | 检查四件套路径 · `rknn-smi info` |
| `RKNN3_QUERY_LLM_CONFIG, size = 184, expect 408` | **头文件与板端 runtime 不一致**。必须用与 `/usr/bin/rknn3_session_test` 同一套 `rknn3-api/include` 重编；编完可在 VM 跑 `echo 'sizeof check' && grep -r rknn3_api.h ${RKNN3_API_PATH}/include` |
| socket 无响应 | `tail -f /userdata/agent/logs/llm_daemon.log` |

### API 版本自检（VM 编译前）

板端 `rknn3_session_test` 能跑时，头文件里的 `sizeof(rknn3_llm_config)` 应为 **408**（1.0.5b10 当前板端）。若你编出的 `llm_daemon` 日志里是 `size=184, expect=408`，说明用了**旧版** `rknn3_api.h`，请改用：

```bash
export RKNN3_API_PATH=~/project/RK182X/rknn/rknn3-api   # 与 session_test_demo Makefile 一致
grep -n rknn3_llm_config ${RKNN3_API_PATH}/include/rknn3_api.h
make clean && make llm_daemon
```
