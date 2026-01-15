from __future__ import annotations

import logging
from fastapi import APIRouter
from fastapi.websockets import WebSocket, WebSocketDisconnect

from inq_service_svc.utils.websocket_manager import manager

logger = logging.getLogger(__name__)

websocket_router = APIRouter()


@websocket_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Simple websocket endpoint: accepts connection, echoes messages, handles ping/pong."""
    try:
        await manager.connect(websocket)
        while True:
            try:
                text = await websocket.receive_text()
            except WebSocketDisconnect:
                # clean disconnect
                manager.disconnect(websocket)
                break
            except Exception as e:
                logger.error(e, exc_info=True)
                manager.disconnect(websocket)
                break

            # keep-alive / echo semantics
            try:
                if text == "ping":
                    await websocket.send_text("pong")
                else:
                    # echo back the received message
                    await websocket.send_text(text)
            except Exception as e:
                logger.error(e, exc_info=True)
                manager.disconnect(websocket)
                break
    except Exception as e:
        logger.error(e, exc_info=True)
