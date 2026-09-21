"""WebSocket endpoint for the live ticket feed."""

from __future__ import annotations

import asyncio
import contextlib
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.events import manager

logger = logging.getLogger(__name__)
router = APIRouter(tags=["realtime"])

# Idle WebSocket connections are routinely killed by proxies and load
# balancers after 30–60 seconds of silence. A periodic frame keeps the
# connection classified as active.
HEARTBEAT_SECONDS = 25


@router.websocket("/ws/tickets")
async def ticket_feed(websocket: WebSocket) -> None:
    """Push ticket events to a connected dashboard.

    Push-only: nothing a client sends mutates state. Incoming messages are
    read solely so a disconnect is noticed promptly, rather than on the next
    broadcast that fails.
    """
    await websocket.accept()

    # Register before announcing readiness, so no event can slip into the gap
    # between the client being told it is live and it actually receiving.
    await manager.register(websocket)
    heartbeat = asyncio.create_task(_heartbeat(websocket))

    try:
        await websocket.send_json({"type": "ready", "data": {}})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("websocket feed error")
    finally:
        heartbeat.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await heartbeat
        await manager.disconnect(websocket)


async def _heartbeat(websocket: WebSocket) -> None:
    """Send a keepalive frame until the socket closes."""
    try:
        while True:
            await asyncio.sleep(HEARTBEAT_SECONDS)
            await websocket.send_json({"type": "ping", "data": {}})
    except (WebSocketDisconnect, RuntimeError):
        # RuntimeError is what Starlette raises when sending on a socket that
        # has already closed — an expected race, not an error worth logging.
        pass
