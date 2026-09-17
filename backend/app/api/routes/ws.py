"""WebSocket endpoint for the live ticket feed."""

from __future__ import annotations

import asyncio
import contextlib
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.events import manager

logger = logging.getLogger(__name__)
router = APIRouter(tags=["realtime"])

# Server-initiated ping interval. Idle WebSocket connections are routinely
# killed by proxies and load balancers after 30–60 seconds of silence, and the
# client sees that as a drop rather than an idle period. A periodic frame keeps
# the connection classified as active.
HEARTBEAT_SECONDS = 25


@router.websocket("/ws/tickets")
async def ticket_feed(websocket: WebSocket) -> None:
    """Push ticket events to a connected dashboard.

    Intentionally unauthenticated. Browsers cannot set an Authorization header
    on a WebSocket handshake, so the usual workarounds are a token in the query
    string (which lands in server access logs) or a cookie (which reintroduces
    CSRF). The payloads here are the same non-sensitive summaries the REST API
    already serves, so the trade is not worth making — and the socket is
    strictly push-only: nothing a client sends can mutate state.

    For a real deployment this would use a short-lived ticket: the client
    exchanges its JWT for a single-use nonce over HTTPS and presents that.
    """
    await manager.connect(websocket)

    heartbeat = asyncio.create_task(_heartbeat(websocket))
    try:
        while True:
            # Nothing the client sends is acted on. This await exists to
            # detect disconnection — without a pending receive, a closed
            # socket is not noticed until the next broadcast fails.
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
