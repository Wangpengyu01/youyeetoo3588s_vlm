# Voice Dialogue Latency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the voice assistant interruptible and resilient while streaming a natural first spoken clause as early as possible and measuring end-to-end first-play latency.

**Architecture:** The orchestrator owns all mutable stream state on its asyncio loop. A background LLM socket reader forwards only token strings; a turn ID guards each TTS item so obsolete synthesis cannot leak into a later turn. Intent rules live in a small pure module, allowing hardware-free tests.

**Tech Stack:** Python 3.14 standard library `asyncio` and `unittest`; existing sherpa/RKNN3 services; no new dependencies.

**Spec:** `docs/superpowers/specs/2026-09-08-voice-dialog-latency-design.md`

## Global Constraints

- Do not add dependencies or require board-side models in automated tests.
- Retain the existing ChatML prompt and streaming daemon protocol.
- Treat one-second response as VAD-end to first-TTS-play target, not full-answer completion.
- Preserve `mute_mic_during_tts` only as an explicit half-duplex diagnostic mode; default it to `false`.
- Do not expose raw thinking-token content through the WebSocket event stream.

---

### Task 1: Pure conversation policy

**Files:**
- Create: `agent/orchestrator/dialogue_policy.py`
- Create: `agent/tests/test_dialogue_policy.py`
- Modify: `agent/orchestrator/main.py`

**Interfaces:**
- Produces `is_stop_command(text: str) -> bool`, `is_resume_command(text: str) -> bool`, and `can_barge_in(partial_text: str, speech_sec: float, min_speech_sec: float) -> bool`.
- `Orchestrator._run_llm()` and ASR partial callback consume these functions.

- [ ] **Step 1: Write failing policy tests**

```python
class DialoguePolicyTests(unittest.TestCase):
    def test_stop_command_requires_a_complete_command(self):
        self.assertTrue(is_stop_command("停止"))
        self.assertFalse(is_stop_command("停车场在哪里"))

    def test_barge_in_waits_for_configured_speech_duration(self):
        self.assertFalse(can_barge_in("你好", 0.20, 0.25))
        self.assertTrue(can_barge_in("你好", 0.25, 0.25))
```

- [ ] **Step 2: Run tests to verify RED**

Run: `python -m unittest agent.tests.test_dialogue_policy -v`

Expected: FAIL because `orchestrator.dialogue_policy` does not exist.

- [ ] **Step 3: Implement the smallest pure helpers**

```python
def is_stop_command(text: str) -> bool:
    return bool(_STOP_COMMAND.fullmatch(normalize(text)))

def can_barge_in(partial_text: str, speech_sec: float, min_speech_sec: float) -> bool:
    return len(normalize(partial_text)) >= 2 and speech_sec >= min_speech_sec
```

- [ ] **Step 4: Run tests to verify GREEN**

Run: `python -m unittest agent.tests.test_dialogue_policy -v`

Expected: PASS.

- [ ] **Step 5: Wire policy helpers into the orchestrator**

Replace inline stop/resume regexes. Clear `_paused_relay_text` before the stop acknowledgement. Permit a stop command to interrupt immediately; require `can_barge_in()` for ordinary partial speech.

### Task 2: Generation-isolated TTS

**Files:**
- Modify: `agent/tts/tts_queue.py`
- Create: `agent/tests/test_tts_queue.py`

**Interfaces:**
- `mark_utterance_start(generation: int) -> None`
- `enqueue(text: str, *, generation: int) -> None`
- `wait_done(generation: int) -> None`
- `stop() -> None`

- [ ] **Step 1: Write failing stale-generation test**

```python
async def test_old_synthesis_cannot_play_after_a_new_generation_starts(self):
    queue = TtsQueue(BlockingFakeEngine())
    await queue.start()
    queue.mark_utterance_start(1)
    await queue.enqueue("旧回答", generation=1)
    await engine.wait_until_synthesis_started()
    await queue.interrupt()
    queue.mark_utterance_start(2)
    await queue.enqueue("新回答", generation=2)
    engine.release_synthesis()
    await queue.wait_done(2)
    self.assertEqual(engine.played_texts, ["新回答"])
```

- [ ] **Step 2: Run test to verify RED**

Run: `python -m unittest agent.tests.test_tts_queue -v`

Expected: FAIL because generation arguments are unsupported and stale output can play.

- [ ] **Step 3: Add generation to queued text and wav records**

Store a generation alongside each queued text/wav. Workers discard an item whenever it is not the active generation both before and after the blocking synth/play call. Do not save the currently playing clause as relay text.

- [ ] **Step 4: Run test to verify GREEN**

Run: `python -m unittest agent.tests.test_tts_queue -v`

Expected: PASS.

- [ ] **Step 5: Add lifecycle shutdown**

`stop()` enqueues worker sentinels, awaits both worker tasks, and clears task references. The method must be idempotent.

### Task 3: Event-loop-owned streaming and service lifecycle

**Files:**
- Modify: `agent/orchestrator/main.py`
- Create: `agent/tests/test_orchestrator_workers.py`

**Interfaces:**
- `_turn_worker()` accepts `None` as a shutdown sentinel.
- `_process_turn(event)` assigns a monotonically increasing generation.
- `_run_llm(user_text, *, generation, vad_end_at)` sends tokens through an asyncio queue and only the event loop mutates `StreamingSentenceSplitter`.

- [ ] **Step 1: Write failing worker lifecycle tests**

```python
async def test_turn_worker_stops_after_sentinel(self):
    orch = lightweight_orchestrator()
    await orch._turn_queue.put(None)
    await asyncio.wait_for(orch._turn_worker(), timeout=0.1)

async def test_turn_worker_reports_one_failure_and_processes_next_turn(self):
    orch = lightweight_orchestrator(process=[RuntimeError("boom"), None])
    await orch._turn_queue.put({"type": "audio_segment"})
    await orch._turn_queue.put({"type": "audio_segment"})
    await orch._turn_queue.put(None)
    await orch._turn_worker()
    self.assertEqual(orch.processed, 2)
    self.assertEqual(orch.errors, ["turn_failed"])
```

- [ ] **Step 2: Run tests to verify RED**

Run: `python -m unittest agent.tests.test_orchestrator_workers -v`

Expected: FAIL because the worker has no sentinel or per-turn exception handling.

- [ ] **Step 3: Implement bounded latest-turn queuing and worker recovery**

Use `asyncio.Queue(maxsize=2)`. On overflow, remove queued stale segments before accepting the newest one. Catch exceptions around one `_process_turn()` call, emit `{\"type\": \"error\", \"code\": \"turn_failed\"}`, restore LISTEN state, then continue. Add a sentinel after VAD shutdown and close TTS/WebSocket resources in `run()` finally.

- [ ] **Step 4: Move token handling to the event loop**

Use `loop.call_soon_threadsafe(token_queue.put_nowait, piece)` in the synchronous daemon callback. Consume that queue in `_run_llm()`, stream complete clauses directly to `_enqueue_speak(..., generation=generation)`, and coalesce `llm_token` UI events on a 40 ms window. Reject tokens from obsolete generations.

- [ ] **Step 5: Emit latency telemetry and run tests to verify GREEN**

Record VAD-end time when queueing a segment, first token time when received, and `TtsQueue.first_play_at` when playback begins. Emit one `latency` event with millisecond values after the turn. Run: `python -m unittest agent.tests.test_orchestrator_workers agent.tests.test_dialogue_policy agent.tests.test_tts_queue -v`.

Expected: PASS.

### Task 4: Default configuration and final verification

**Files:**
- Modify: `agent/config/agent.yaml`
- Modify: `agent/orchestrator/README.md`
- Modify: `agent/docs/PHASE_G.md`

- [ ] **Step 1: Set interactive defaults and document trade-offs**

Set `vad.mute_mic_during_tts: false`. Document that `true` is a diagnostic half-duplex mode that disables barge-in. Document current limitation: daemon-side cancellation requires a future RKNN3 abort API.

- [ ] **Step 2: Run the complete hardware-free test suite**

Run: `python -m unittest discover -s agent/tests -v`.

Expected: all tests pass.

- [ ] **Step 3: Compile all Python sources**

Run: `python -m compileall -q agent`.

Expected: exit code 0.

- [ ] **Step 4: Inspect final diff**

Run: `git diff --check` and `git diff --stat`.

Expected: no whitespace errors and only planned files changed.
