from typing import Dict

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from app.core.logging.logger import get_logger
from app.core.observability.metrics import WS_CONNECTIONS, WS_MESSAGES

logger = get_logger("ai_os.streaming.connection_manager")


class ConnectionManager:
    def __init__(self):
        self._connections: Dict[str, WebSocket] = {}

    async def connect(
        self, websocket: WebSocket, user_id: str, session_id: str
    ) -> None:
        self.cleanup_stale_connections()
        await websocket.accept()
        self._connections[f"{user_id}:{session_id}"] = websocket
        WS_CONNECTIONS.inc()
        logger.info("ws_connected", user_id=user_id, session_id=session_id)

    def disconnect(self, user_id: str, session_id: str) -> None:
        key = f"{user_id}:{session_id}"
        if key in self._connections:
            self._connections.pop(key, None)
            WS_CONNECTIONS.dec()

    async def send_event(self, user_id: str, session_id: str, event: dict) -> None:
        ws = self._connections.get(f"{user_id}:{session_id}")
        if ws:
            try:
                await ws.send_json(event)
                WS_MESSAGES.labels(direction="sent").inc()
            except Exception:
                self.disconnect(user_id, session_id)

    async def broadcast_to_user(self, user_id: str, event: dict) -> None:
        keys = [k for k in self._connections if k.startswith(f"{user_id}:")]
        for key in keys:
            uid, sid = key.split(":", 1)
            await self.send_event(uid, sid, event)

    def is_connected(self, user_id: str, session_id: str) -> bool:
        return f"{user_id}:{session_id}" in self._connections

    def active_count(self) -> int:
        return len(self._connections)

    def cleanup_stale_connections(self) -> None:
        stale_keys = []
        for key, ws in list(self._connections.items()):
            if (
                ws.client_state == WebSocketState.DISCONNECTED
                or ws.application_state == WebSocketState.DISCONNECTED
            ):
                stale_keys.append(key)
        for key in stale_keys:
            if key in self._connections:
                self._connections.pop(key, None)
                WS_CONNECTIONS.dec()
                logger.warning("ws_stale_cleanup", connection_key=key)


connection_manager = ConnectionManager()
