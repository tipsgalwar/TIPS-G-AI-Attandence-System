import asyncio
from collections import defaultdict
from typing import DefaultDict, Set, Tuple

from fastapi import WebSocket
from loguru import logger


class InAppPushManager:
    """Keeps lightweight WebSocket connections for signed-in desktop clients."""

    def __init__(self):
        self.connections: DefaultDict[Tuple[str, int], Set[WebSocket]] = defaultdict(set)
        self.loop = None

    async def connect(self, websocket: WebSocket, role: str, user_id: int):
        await websocket.accept()
        self.loop = asyncio.get_running_loop()
        self.connections[(role, user_id)].add(websocket)

    def disconnect(self, websocket: WebSocket, role: str, user_id: int):
        clients = self.connections.get((role, user_id))
        if clients:
            clients.discard(websocket)
            if not clients:
                self.connections.pop((role, user_id), None)

    async def _send(self, role: str, user_id: int, payload: dict):
        for websocket in list(self.connections.get((role, user_id), set())):
            try:
                await websocket.send_json(payload)
            except Exception:
                self.disconnect(websocket, role, user_id)

    def push(self, role: str, user_id: int, payload: dict):
        """Schedule delivery from either a FastAPI async route or sync worker."""
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self._send(role, user_id, payload), self.loop)
        else:
            logger.debug("No desktop notification socket is currently connected.")


in_app_push_manager = InAppPushManager()