import logging
from unittest.mock import AsyncMock

import pytest

from inq_service_svc.utils.websocket_manager import ConnectionManager


class DummyWebSocket:
    def __init__(self):
        # async methods
        self.accept = AsyncMock()
        self.send_text = AsyncMock()

    def __hash__(self):
        # make instances hashable so they can be stored in a set
        return id(self)

    def __repr__(self):
        return f"<DummyWebSocket {id(self)}>"


@pytest.mark.anyio
async def test_connect_adds_connection_and_accept_called():
    manager = ConnectionManager()
    ws = DummyWebSocket()
    await manager.connect(ws)
    ws.accept.assert_awaited_once()
    assert ws in manager.active_connections


@pytest.mark.anyio
async def test_disconnect_removes_connection():
    manager = ConnectionManager()
    ws = DummyWebSocket()
    await manager.connect(ws)
    manager.disconnect(ws)
    assert ws not in manager.active_connections


@pytest.mark.anyio
async def test_broadcast_sends_to_all_connections():
    manager = ConnectionManager()
    ws1 = DummyWebSocket()
    ws2 = DummyWebSocket()
    await manager.connect(ws1)
    await manager.connect(ws2)
    await manager.broadcast("hello")
    ws1.send_text.assert_awaited_once_with("hello")
    ws2.send_text.assert_awaited_once_with("hello")


@pytest.mark.anyio
async def test_broadcast_logs_and_continues_on_send_error(caplog):
    manager = ConnectionManager()
    ws1 = DummyWebSocket()
    ws2 = DummyWebSocket()
    # make first websocket raise on send
    ws1.send_text.side_effect = Exception("boom")
    await manager.connect(ws1)
    await manager.connect(ws2)
    with caplog.at_level(logging.ERROR):
        await manager.broadcast("msg")
    # second websocket still received
    ws2.send_text.assert_awaited_once_with("msg")
    # error was logged
    assert any("boom" in rec.getMessage() for rec in caplog.records)
