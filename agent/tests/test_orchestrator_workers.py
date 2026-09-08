from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from orchestrator.main import Orchestrator  # noqa: E402


def lightweight_orchestrator(outcomes: list[Exception | None] | None = None) -> Orchestrator:
    orch = object.__new__(Orchestrator)
    orch._turn_queue = asyncio.Queue(maxsize=2)
    orch.processed: list[object] = []
    orch.errors: list[dict] = []
    pending_outcomes = list(outcomes or [])

    async def process(event: object) -> None:
        orch.processed.append(event)
        if pending_outcomes:
            outcome = pending_outcomes.pop(0)
            if outcome:
                raise outcome

    async def emit(event: dict) -> None:
        orch.errors.append(event)

    orch._process_turn = process  # type: ignore[method-assign]
    orch.emit = emit  # type: ignore[method-assign]
    orch.set_state = lambda state: None  # type: ignore[method-assign]
    return orch


class TurnWorkerTests(unittest.IsolatedAsyncioTestCase):
    async def test_turn_worker_stops_after_sentinel(self) -> None:
        orch = lightweight_orchestrator()
        await orch._turn_queue.put(None)
        await asyncio.wait_for(orch._turn_worker(), timeout=0.1)
        self.assertEqual(orch.processed, [])

    async def test_turn_worker_reports_one_failure_and_processes_next_turn(self) -> None:
        orch = lightweight_orchestrator([RuntimeError("boom"), None])
        first = {"id": 1}
        second = {"id": 2}
        await orch._turn_queue.put(first)
        await orch._turn_queue.put(second)

        with self.assertLogs("orchestrator", level="ERROR"):
            worker = asyncio.create_task(orch._turn_worker())
            await asyncio.sleep(0)
            await orch._turn_queue.put(None)
            await asyncio.wait_for(worker, timeout=0.1)

        self.assertEqual(orch.processed, [first, second])
        self.assertEqual(orch.errors, [{"type": "error", "code": "turn_failed"}])

    async def test_latest_turn_replaces_old_queued_turn_when_queue_is_full(self) -> None:
        orch = lightweight_orchestrator()
        await orch._enqueue_turn({"id": 1})
        await orch._enqueue_turn({"id": 2})
        await orch._enqueue_turn({"id": 3})

        first = orch._turn_queue.get_nowait()
        second = orch._turn_queue.get_nowait()
        self.assertEqual([first["id"], second["id"]], [2, 3])


if __name__ == "__main__":
    unittest.main()
