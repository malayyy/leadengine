import json
import logging
from typing import Set
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class WebSocketManager:
    def __init__(self):
        self._connections: dict[int, Set[WebSocket]] = {}

    async def connect(self, job_id: int, websocket: WebSocket):
        await websocket.accept()
        if job_id not in self._connections:
            self._connections[job_id] = set()
        self._connections[job_id].add(websocket)
        logger.info(f"WebSocket connected for job {job_id} (total: {len(self._connections[job_id])})")

    async def disconnect(self, job_id: int, websocket: WebSocket):
        if job_id in self._connections:
            self._connections[job_id].discard(websocket)
            if not self._connections[job_id]:
                del self._connections[job_id]
        logger.info(f"WebSocket disconnected for job {job_id}")

    async def broadcast(self, job_id: int, event: dict):
        if job_id not in self._connections:
            return
        message = json.dumps(event)
        dead = set()
        for ws in self._connections[job_id]:
            try:
                await ws.send_text(message)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self._connections[job_id].discard(ws)
        if not self._connections.get(job_id):
            self._connections.pop(job_id, None)

    def count(self, job_id: int) -> int:
        return len(self._connections.get(job_id, set()))

    @property
    def total_connections(self) -> int:
        return sum(len(conns) for conns in self._connections.values())


ws_manager = WebSocketManager()
