from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime

from fastapi import WebSocket

from backend.schemas import RealtimeEvent


class RealtimeHub:
    def __init__(self) -> None:
        self.connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self.connections.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self.connections.discard(websocket)
        with contextlib.suppress(Exception):
            await websocket.close()

    async def broadcast(self, event: RealtimeEvent) -> None:
        stale_connections: list[WebSocket] = []
        async with self._lock:
            for websocket in self.connections:
                try:
                    await websocket.send_json(event.model_dump(mode="json"))
                except Exception:
                    stale_connections.append(websocket)
            for websocket in stale_connections:
                self.connections.discard(websocket)

    async def ping(self) -> None:
        await self.broadcast(
            RealtimeEvent(type="ping", timestamp=datetime.now(UTC), symbols=[])
        )
