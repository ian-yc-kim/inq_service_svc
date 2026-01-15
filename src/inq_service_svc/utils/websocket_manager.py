import logging
from typing import Set

from fastapi.websockets import WebSocket

_logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manage active WebSocket connections and broadcast messages.

    Stores connections in an in-memory set. Methods are safe and log exceptions.
    """

    def __init__(self) -> None:
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        """Accept an incoming websocket connection and track it."""
        try:
            await websocket.accept()
            # Use add; websocket objects must be hashable in typical FastAPI usage
            self.active_connections.add(websocket)
        except Exception as e:
            _logger.error(e, exc_info=True)
            raise

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a websocket connection from tracking. No-op if not present."""
        # set.discard does not raise; keep implementation simple
        self.active_connections.discard(websocket)

    async def broadcast(self, message: str) -> None:
        """Send text message to all active connections.

        On individual send failures, log details and remove the failing connection.
        """
        to_remove = []
        for ws in list(self.active_connections):
            try:
                await ws.send_text(message)
            except Exception as e:
                _logger.error(e, exc_info=True)
                to_remove.append(ws)

        for ws in to_remove:
            try:
                self.disconnect(ws)
            except Exception as e:
                _logger.error(e, exc_info=True)


# Module-level singleton manager used by routers to broadcast events
manager = ConnectionManager()
