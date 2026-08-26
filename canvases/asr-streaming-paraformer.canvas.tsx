import {
  BarChart,
  Callout,
  Card,
  CardBody,
  CardHeader,
  Code,
  Divider,
  Grid,
  H1,
  H2,
  H3,
  Pill,
  Row,
  Stack,
  Stat,
  Table,
  Text,
  TodoList,
} from "cursor/canvas";

const LATENCY = {
  categories: ["ASR", "LLM TTFT", "TTS Matcha", "Play"],
  before: [7000, 100, 1500, 500],
  target: [800, 100, 1500, 500],
};

const GITHUB_REPOS = [
  [
    "k2-fsa/sherpa-onnx",
    "官方引擎 · RK3588 预编译 · OnlineRecognizer C/Python API",
    "https://github.com/k2-fsa/sherpa-onnx",
  ],
  [
    "streaming-paraformer-c-api.c",
    "Paraformer 流式 C API 示例（本方案参照）",
    "https://github.com/k2-fsa/sherpa-onnx/blob/master/c-api-examples/streaming-paraformer-c-api.c",
  ],
  [
    "streaming-paraformer-asr-microphone.py",
    "麦克风实时流式 Python 示例",
    "https://github.com/k2-fsa/sherpa-onnx/blob/master/python-api-examples/streaming-paraformer-asr-microphone.py",
  ],
  [
    "ruzhila/voiceapi",
    "FastAPI 封装 sherpa ASR+TTS 服务",
    "https://github.com/ruzhila/voiceapi",
  ],
  [
    "roomkit voice_local_onnx_vllm.py",
    "VAD + streaming STT + LLM + TTS 全本地 pipeline",
    "https://github.com/roomkit-live/roomkit/blob/main/examples/voice_local_onnx_vllm.py",
  ],
  [
    "Ponyu-dev/Unity-Sherpa-ONNX",
    "Unity 插件 · Silero VAD + streaming Paraformer 池化",
    "https://github.com/Ponyu-dev/Unity-Sherpa-ONNX",
  ],
];

const COMPARE = [
  ["维度", "SenseVoice offline", "Streaming Paraformer"],
  ["运行方式", "每轮 subprocess 整段解码", "OnlineRecognizer 常驻 C API"],
  ["partial", "假流式 · 反复全量 offline", "真流式 · AcceptWaveform + Decode"],
  ["典型延迟", "~7s / 句", "目标 <1s final · partial 边说边出"],
  ["模型体积", "~230MB int8", "~226MB int8 encoder+decoder"],
  ["联网", "完全离线", "完全离线"],
  ["端点", "Silero VAD（不变）", "Silero VAD · enable_endpoint=0"],
];

const TODOS = [
  { id: "f1", content: "GitHub 调研 + Canvas + TECH_PLAN 更新", status: "completed" as const },
  { id: "f2", content: "sherpa_streaming_asr.py OnlineRecognizer ctypes", status: "completed" as const },
  { id: "f3", content: "asr_engine / orchestrator / agent.yaml 接线", status: "completed" as const },
  { id: "f4", content: "install_streaming_asr.sh + phase_f_test.sh", status: "completed" as const },
  { id: "f5", content: "板端下载模型 (~1GB) + adb push", status: "in_progress" as const },
  { id: "f6", content: "phase_f_test 验收 first_play < 5s", status: "pending" as const },
];

export default function AsrStreamingParaformerCanvas() {
  return (
    <Stack gap="lg">
      <Row align="center" gap="md">
        <H1>Phase F — Streaming Paraformer ASR</H1>
        <Pill active tone="info">
          进行中
        </Pill>
      </Row>
      <Text size="small" tone="muted">
        youyeetoo R1 · RK3588S · sherpa-onnx v1.12.8 · 目标 first_play &lt; 5s
      </Text>

      <Callout tone="info" title="为什么换 ASR">
        当前 SenseVoice 每轮启动 sherpa-onnx-offline subprocess，整段识别约 7s，是 first_play ~10s 的主瓶颈。
        Matcha TTS 已优化到 ~0.5s/句；下一步用 Paraformer OnlineRecognizer 真流式 ASR。
      </Callout>

      <Grid columns={3} gap="md">
        <Card>
          <CardHeader>ASR 现状</CardHeader>
          <CardBody>
            <Stat label="SenseVoice offline" value="~7s" tone="danger" />
          </CardBody>
        </Card>
        <Card>
          <CardHeader>ASR 目标</CardHeader>
          <CardBody>
            <Stat label="Paraformer streaming" value="<1s" tone="success" />
          </CardBody>
        </Card>
        <Card>
          <CardHeader>E2E 目标</CardHeader>
          <CardBody>
            <Stat label="first_play" value="<5s" tone="info" />
          </CardBody>
        </Card>
      </Grid>

      <H2>延迟对比（ms）</H2>
      <Text size="small" tone="muted">
        Source: 板端 orchestrator 日志 · 2026-08-26 · Matcha TTS 已部署
      </Text>
      <BarChart
        categories={LATENCY.categories}
        series={[
          { name: "SenseVoice 优化前", data: LATENCY.before, tone: "danger" },
          { name: "Paraformer 目标", data: LATENCY.target, tone: "success" },
        ]}
        height={220}
        valueSuffix="ms"
      />

      <H2>方案对比</H2>
      <Table headers={COMPARE[0]} rows={COMPARE.slice(1)} striped />

      <H2>数据流</H2>
      <Code>{`Mic → Silero VAD (不变)
speech_start → OnlineStream.reset()
audio_chunk  → AcceptWaveform → Decode → asr_partial (文本变化)
speech_end   → InputFinished → final → LLM → Matcha TTS → play`}</Code>

      <H2>GitHub 参考项目</H2>
      <Table
        headers={["仓库", "说明", "链接"]}
        rows={GITHUB_REPOS.map((r) => [r[0], r[1], r[2]])}
        striped
      />

      <Divider />

      <H2>板端路径</H2>
      <Code>{`/userdata/voice/sherpa-onnx-streaming-paraformer-bilingual-zh-en/
├── encoder.int8.onnx
├── decoder.int8.onnx
└── tokens.txt

agent/asr/sherpa_streaming_asr.py   # OnlineRecognizer C API
agent/config/agent.yaml             # asr.backend: streaming_paraformer`}</Code>

      <H2>实施清单</H2>
      <TodoList todos={TODOS} />

      <Callout tone="warning" title="回退">
        agent.yaml 改 <Code>asr.backend: sense_voice</Code> 并恢复 SenseVoice model_dir 即可回退，无需删模型。
      </Callout>
    </Stack>
  );
}
