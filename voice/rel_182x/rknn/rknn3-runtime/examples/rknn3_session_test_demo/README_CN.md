# Session 测试用例说明
此工程提供 4 个 Session 测试用例：

1. rknn3_session_test  
   通用 Session 推理示例，用于演示基于典型的 prompt 输入的推理流程。
2. rknn3_session_test_token_embed_input  
   基于 token/embed 输入接口的推理示例，可用于非 prompt 输入类型的推理场景。
3. rknn3_session_test_eval_perf  
   性能评估示例，用于评估 LLM 模型的 TPS/TTFT 等核心性能指标。
4. rknn3_session_test_function_call  
   支持 Function Calling 特性的推理示例，用于演示大模型在实际函数调用场景下的推理方式。

## Linux 平台使用示例

### 编译

```sh
# 请先指定编译器路径
(optional)export GCC_COMPILER=<GCC_COMPILER_PATH>

./build-linux.sh -t <TARGET_PLATFORM> -a <ARCH> [-b <build_type>]

# 例如
./build-linux.sh -t rk3588 -a aarch64 -b Release
```

### install 目录库文件说明

编译并执行 `make install` 后，`install/rknn3_session_test_RK3588_Linux/lib` 中会按平台安装以下库：

- RK3576 / RK3588：`librknn3_api.so` + `librknn3_api_rkcp.so`
- RK3572：`librknn3_api.so` + `librknn3_api_native.so`

### 推送到板端

```sh
adb push install/rknn3_llm_test_<TARGET_PLATFORM>_Linux/ /data/
```

### 运行

```sh
adb shell
cd /data/rknn3_llm_test_<TARGET_PLATFORM>_Linux

export LD_LIBRARY_PATH=./lib

# Usage: ./rknn3_session_test <rknn_path> <weight_path> <tokenizer.gguf> <embedding.bin> <max_context_len> <max_new_tokens> <core_mask>
./rknn3_session_test Qwen2.5-0.5B.rknn Qwen2.5-0.5B.weight Qwen2.5-0.5B.tokenizer.gguf Qwen2.5-0.5B.embed.bin 2048 512 0xff

# Usage: ./rknn3_session_test_token_embed_input <rknn_path> <weight_path> <tokenizer.gguf> <embedding.bin> <max_context_len> <max_new_tokens> <core_mask>
./rknn3_session_test_token_embed_input Qwen2.5-0.5B.rknn Qwen2.5-0.5B.weight Qwen2.5-0.5B.tokenizer.gguf Qwen2.5-0.5B.embed.bin 2048 512 0xff

# Usage: ./rknn3_session_test_eval_perf <rknn_path> <weight_path> <tokenizer.gguf> <embedding.bin> <max_context_len> <n_input_tokens> <max_new_tokens> <core_mask>
./rknn3_session_test_eval_perf Qwen2.5-0.5B.rknn Qwen2.5-0.5B.weight Qwen2.5-0.5B.tokenizer.gguf Qwen2.5-0.5B.embed.bin 2048 128 128 0xff

# Usage: ./rknn3_session_test_function_call <rknn_path> <weight_path> <tokenizer.gguf> <embedding.bin> <max_context_len> <max_new_tokens> <core_mask>
./rknn3_session_test_function_call Qwen2.5-0.5B.rknn Qwen2.5-0.5B.weight Qwen2.5-0.5B.tokenizer.gguf Qwen2.5-0.5B.embed.bin 2048 512 0xff
```
参数说明: 
- `rknn_path`: rknn 文件路径
- `weight_path`: weight 文件路径
- `tokenizer.gguf`: tokenizer.gguf 文件路径
- `embedding.bin`: embedding.bin 文件路径
- `max_context_len`: 模型转换时 `rknn.config` 中配置的 max_ctx_len 值
- `n_input_tokens`: 输入的 token 数
- `max_new_tokens`: 每次会话最多生成的 token 数
- `core_mask`: 目前有 8 个核，对应 8 bit 数，使用哪一个核，就将哪一位置 1，例如使用核 0 和核 1，就将第 0 位和第 1 位置 1，得到的二进制数是0b11，对应的十六进制数是 0x3，core_mask 设置成 0x3


## Android 平台使用示例

### 编译

```sh
# 请先指定编译器路径
(optional)export ANDROID_NDK_PATH=<ANDROID_NDK_PATH>

./build-android.sh -t <TARGET_PLATFORM> -a <ARCH> [-b <build_type>]

# 例如
./build-android.sh -t rk3588 -a arm64-v8a -b Release
```

### install 目录库文件说明

编译并执行 `make install` 后，`install/rknn3_session_test_RK3588_Android/lib` 中会按平台安装以下库：

- RK3576 / RK3588：`librknn3_api.so` + `librknn3_api_rkcp.so`
- RK3572：`librknn3_api.so` + `librknn3_api_native.so`

### 推送到板端

```sh
adb root
adb remount
adb push install/rknn3_llm_test_<TARGET_PLATFORM>_Android/ /data/
```

### 运行

```sh
adb shell
cd /data/rknn3_llm_test_<TARGET_PLATFORM>_Linux

export LD_LIBRARY_PATH=./lib

# Usage: ./rknn3_session_test <rknn_path> <weight_path> <tokenizer.gguf> <embedding.bin> <max_context_len> <max_new_tokens> <core_mask>
./rknn3_session_test Qwen2.5-0.5B.rknn Qwen2.5-0.5B.weight Qwen2.5-0.5B.tokenizer.gguf Qwen2.5-0.5B.embed.bin 2048 512 0xff

# Usage: ./rknn3_session_test_token_embed_input <rknn_path> <weight_path> <tokenizer.gguf> <embedding.bin> <max_context_len> <max_new_tokens> <core_mask>
./rknn3_session_test_token_embed_input Qwen2.5-0.5B.rknn Qwen2.5-0.5B.weight Qwen2.5-0.5B.tokenizer.gguf Qwen2.5-0.5B.embed.bin 2048 512 0xff

# Usage: ./rknn3_session_test_eval_perf <rknn_path> <weight_path> <tokenizer.gguf> <embedding.bin> <max_context_len> <n_input_tokens> <max_new_tokens> <core_mask>
./rknn3_session_test_eval_perf Qwen2.5-0.5B.rknn Qwen2.5-0.5B.weight Qwen2.5-0.5B.tokenizer.gguf Qwen2.5-0.5B.embed.bin 2048 128 128 0xff

# Usage: ./rknn3_session_test_function_call <rknn_path> <weight_path> <tokenizer.gguf> <embedding.bin> <max_context_len> <max_new_tokens> <core_mask>
./rknn3_session_test_function_call Qwen2.5-0.5B.rknn Qwen2.5-0.5B.weight Qwen2.5-0.5B.tokenizer.gguf Qwen2.5-0.5B.embed.bin 2048 512 0xff
```
参数说明: 
- `rknn_path`: rknn 文件路径
- `weight_path`: weight 文件路径
- `tokenizer.gguf`: tokenizer.gguf 文件路径
- `embedding.bin`: embedding.bin 文件路径
- `max_context_len`: 模型转换时 `rknn.config` 中配置的 max_ctx_len 值
- `n_input_tokens`: 输入的 token 数
- `max_new_tokens`: 每次会话最多生成的 token 数
- `core_mask`: 目前有 8 个核，对应 8 bit 数，使用哪一个核，就将哪一位置 1，例如使用核 0 和核 1，就将第 0 位和第 1 位置 1，得到的二进制数是0b11，对应的十六进制数是 0x3，core_mask 设置成 0x3

# Windows 平台使用示例（Cygwin）

## 编译

在 Windows Cygwin 环境下，执行如下命令：

```sh
./build-cygwin.sh -t <TARGET_PLATFORM> [-b <build_type>]

# 例如：
./build-cygwin.sh -t rk3588 -b Release
```

**注意：**
- 需要在 Cygwin 终端中运行构建脚本
- 确保已安装 Cygwin 的编译工具链（gcc、g++、make 等）
- 目标平台参数必须小写（如 rk3588、rk3576）

## install 目录库文件说明

编译并执行 `make install` 后，`install/rknn3_session_test_RK3588_windows/lib` 中会按平台安装以下库：

- RK3576 / RK3588：`librknn3_api.dll` + `librknn3_api_rkcp.dll`
- RK3572：`librknn3_api.dll` + `librknn3_api_native.dll`

## 运行

在 Cygwin 终端或 Windows 命令行中运行：

```sh
# 方式 1: Cygwin 终端
cd install/rknn3_session_test_RK3588_windows/
export PATH=./lib:$PATH

# Usage: ./rknn3_session_test.exe <rknn_path> <weight_path> <tokenizer.gguf> <embedding.bin> <max_context_len> <max_new_tokens> <core_mask>
./rknn3_session_test.exe Qwen2.5-0.5B.rknn Qwen2.5-0.5B.weight Qwen2.5-0.5B.tokenizer.gguf Qwen2.5-0.5B.embed.bin 2048 512 0xff

# Usage: ./rknn3_session_test_token_embed_input.exe <rknn_path> <weight_path> <tokenizer.gguf> <embedding.bin> <max_context_len> <max_new_tokens> <core_mask>
./rknn3_session_test_token_embed_input.exe Qwen2.5-0.5B.rknn Qwen2.5-0.5B.weight Qwen2.5-0.5B.tokenizer.gguf Qwen2.5-0.5B.embed.bin 2048 512 0xff

# Usage: ./rknn3_session_test_eval_perf.exe <rknn_path> <weight_path> <tokenizer.gguf> <embedding.bin> <max_context_len> <n_input_tokens> <max_new_tokens> <core_mask>
./rknn3_session_test_eval_perf.exe Qwen2.5-0.5B.rknn Qwen2.5-0.5B.weight Qwen2.5-0.5B.tokenizer.gguf Qwen2.5-0.5B.embed.bin 2048 128 128 0xff

# Usage: ./rknn3_session_test_function_call.exe <rknn_path> <weight_path> <tokenizer.gguf> <embedding.bin> <max_context_len> <max_new_tokens> <core_mask>
./rknn3_session_test_function_call.exe Qwen2.5-0.5B.rknn Qwen2.5-0.5B.weight Qwen2.5-0.5B.tokenizer.gguf Qwen2.5-0.5B.embed.bin 2048 512 0xff

# 方式 2: Windows 命令行 (cmd/PowerShell)
cd install\rknn3_session_test_RK3588_windows
set PATH=.\lib;%PATH%

# Usage: rknn3_session_test.exe <rknn_path> <weight_path> <tokenizer.gguf> <embedding.bin> <max_context_len> <max_new_tokens> <core_mask>
rknn3_session_test.exe Qwen2.5-0.5B.rknn Qwen2.5-0.5B.weight Qwen2.5-0.5B.tokenizer.gguf Qwen2.5-0.5B.embed.bin 2048 512 0xff

# Usage: rknn3_session_test_token_embed_input.exe <rknn_path> <weight_path> <tokenizer.gguf> <embedding.bin> <max_context_len> <max_new_tokens> <core_mask>
rknn3_session_test_token_embed_input.exe Qwen2.5-0.5B.rknn Qwen2.5-0.5B.weight Qwen2.5-0.5B.tokenizer.gguf Qwen2.5-0.5B.embed.bin 2048 512 0xff

# Usage: rknn3_session_test_eval_perf.exe <rknn_path> <weight_path> <tokenizer.gguf> <embedding.bin> <max_context_len> <n_input_tokens> <max_new_tokens> <core_mask>
rknn3_session_test_eval_perf.exe Qwen2.5-0.5B.rknn Qwen2.5-0.5B.weight Qwen2.5-0.5B.tokenizer.gguf Qwen2.5-0.5B.embed.bin 2048 128 128 0xff

# Usage: rknn3_session_test_function_call.exe <rknn_path> <weight_path> <tokenizer.gguf> <embedding.bin> <max_context_len> <max_new_tokens> <core_mask>
rknn3_session_test_function_call.exe Qwen2.5-0.5B.rknn Qwen2.5-0.5B.weight Qwen2.5-0.5B.tokenizer.gguf Qwen2.5-0.5B.embed.bin 2048 512 0xff
```

参数说明： 
- `rknn_path`: rknn 文件路径
- `weight_path`: weight 文件路径
- `tokenizer.gguf`: tokenizer.gguf 文件路径
- `embedding.bin`: embedding.bin 文件路径
- `max_context_len`: 模型转换时 `rknn.config` 中配置的 max_ctx_len 值
- `n_input_tokens`: 输入的 token 数
- `max_new_tokens`: 每次会话最多生成的 token 数
- `core_mask`: 目前有 8 个核，对应 8 bit 数，使用哪一个核，就将哪一位置 1，例如使用核 0 和核 1，就将第 0 位和第 1 位置 1，得到的二进制数是 0b11，对应的十六进制数是 0x3，core_mask 设置成 0x3

**注：**
1. **Windows 平台下路径分隔符使用反斜杠 `\`，但在 Cygwin 终端中仍可使用正斜杠 `/`**
2. **确保 DLL 文件所在的 lib 目录已添加到系统 PATH 环境变量中**
