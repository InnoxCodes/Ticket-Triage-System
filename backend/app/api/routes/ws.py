"""WebSocket endpoint for the live ticket feed."""

from __future__ import annotations

import asyncio
import contextlib
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.events import manager
from app.core.security import InvalidTokenError, decode_access_token
from app.db.models import Agent
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)
router = APIRouter(tags=["realtime"])

# Idle WebSocket connections are routinely killed by proxies and load
# balancers after 30–60 seconds of silence. A periodic frame keeps the
# connection classified as active.
HEARTBEAT_SECONDS = 25

AUTH_TIMEOUT_SECONDS = 5

# 4000–4999 is the application-defined close-code range. 4401 mirrors HTTP 401
# so the client can tell "token rejected, stop retrying" apart from a dropped
# network connection that is worth reconnecting.
UNAUTHORIZED_CLOSE_CODE = 4401


@router.websocket("/ws/tickets")
async def ticket_feed(websocket: WebSocket) -> None:
    """Push ticket events to an authenticated dashboard.

    Authentication happens in the first message rather than in the handshake.
    Browsers cannot set an Authorization header on a WebSocket upgrade, and
    the two usual workarounds are both worse: a token in the query string gets
    written to every proxy and server access log, and a cookie needs
    SameSite=None plus CSRF protection once frontend and API sit on different
    origins. So the socket is accepted, the client sends
    ``{"type": "auth", "token": "<jwt>"}``, and nothing is broadcast to it
    until that token checks out. A client that stays silent or sends a bad
    token is closed with 4401.

    After that the channel is push-only: nothing a client sends mutates state.
    """
    await websocket.accept()

    agent_name = await _authenticate(websocket)
    if agent_name is None:
        with contextlib.suppress(RuntimeError):
            await websocket.close(code=UNAUTHORIZED_CLOSE_CODE, reason="Unauthorized")
        return

    # Register before announcing readiness, so no event can slip into the gap
    # between the client being told it is live and it actually receiving.
    await manager.register(websocket)
    heartbeat = asyncio.create_task(_heartbeat(websocket))

    try:
        await websocket.send_json({"type": "ready", "data": {"agent": agent_name}})
        while True:
            # Nothing the client sends is acted on. This await exists to
            # detect disconnection promptly rather than on the next broadcast.
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


async def _authenticate(websocket: WebSocket) -> str | None:
    """Wait for the auth message; return the agent's name, or None if rejected."""
    try:
        message = await asyncio.wait_for(websocket.receive_json(), timeout=AUTH_TIMEOUT_SECONDS)
    except (TimeoutError, WebSocketDisconnect, ValueError, KeyError, RuntimeError):
        return None

    if not isinstance(message, dict) or message.get("type") != "auth":
        return None

    token = message.get("token")
    if not isinstance(token, str) or not token:
        return None

    try:
        agent_id = int(decode_access_token(token)["sub"])
    except (InvalidTokenError, KeyError, TypeError, ValueError):
        return None

    # Same rule as the REST dependency: the token is checked against a live
    # account, so a deleted agent's outstanding tokens stop working here too.
    async with SessionLocal() as session:
        agent = await session.get(Agent, agent_id)
    return agent.name if agent else None


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
