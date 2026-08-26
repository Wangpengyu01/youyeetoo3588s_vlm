"""In-process event bus for orchestrator → WebSocket clients."""
from __future__ import annotations

import asyncio
import json
from typing import Any


class EventBus:
    def __init__(self) -> None:
        self._clients: set[asyncio.Queue[str]] = set()
        self._lock = asyncio.Lock()

    async def subscribe(self) -> asyncio.Queue[str]:
        q: asyncio.Queue[str] = asyncio.Queue(maxsize=256)
        async with self._lock:
            self._clients.add(q)
        return q

    async def unsubscribe(self, q: asyncio.Queue[str]) -> None:
        async with self._lock:
            self._clients.discard(q)

    async def publish(self, event: dict[str, Any]) -> None:
        msg = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
        async with self._lock:
            dead: list[asyncio.Queue[str]] = []
            for q in self._clients:
                try:
                    q.put_nowait(msg)
                except asyncio.QueueFull:
                    dead.append(q)
            for q in dead:
                self._clients.discard(q)
