"""In-process WebSocket broadcast hub.

Why native FastAPI WebSockets rather than Socket.IO: the requirement is
one-way fan-out of small JSON events to browser clients that are all on the
same origin. Socket.IO brings a protocol layer, a server dependency and a
client bundle to solve reconnection and transport fallback — problems that a
~40 line reconnecting client already handles for this use case.

Why WebSockets rather than the 5–10s polling the brief also allowed: the
product claim is that tickets "arrive live". A poll makes that a lie up to
ten seconds at a time, and on a Critical ticket that delay is the entire
feature. The frontend still falls back to polling if the socket drops, so the
board is never stale even when the socket is unavailable.

**Scaling limit, stated plainly:** this hub is per-process. Two workers means
a client connected to worker A never sees an event published on worker B.
Fixing it is a Redis pub/sub backplane, and until there is a reason to run
more than one worker, adding Redis would be infrastructure with no user.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class EventType(StrEnum):
    """Event names shared with the frontend's TypeScript union."""

    TICKET_CREATED = "ticket.created"
    TICKET_UPDATED = "ticket.updated"
    TICKET_OVERRIDDEN = "ticket.overridden"
    STATS_INVALIDATED = "stats.invalidated"


class ConnectionManager:
    """Tracks live sockets and fans events out to all of them."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        # Guards the set against concurrent mutation. Broadcasts iterate it
        # while connect/disconnect handlers mutate it from other tasks.
        self._lock = asyncio.Lock()

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    async def connect(self, websocket: WebSocket) -> None:
        """Accept a socket and start tracking it."""
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)
        logger.info("websocket connected (%d live)", len(self._connections))

    async def disconnect(self, websocket: WebSocket) -> None:
        """Stop tracking a socket. Safe to call more than once."""
        async with self._lock:
            self._connections.discard(websocket)
        logger.info("websocket disconnected (%d live)", len(self._connections))

    async def broadcast(self, event: EventType, payload: dict[str, Any]) -> None:
        """Send one event to every live client.

        A send can fail because the peer vanished without a close frame. Those
        sockets are collected and dropped rather than allowed to raise into
        the caller — a browser being closed must never fail the API request
        that happened to trigger the broadcast.
        """
        async with self._lock:
            targets = list(self._connections)

        if not targets:
            return

        message = {
            "type": event.value,
            "timestamp": datetime.now(UTC).isoformat(),
            "data": payload,
        }

        results = await asyncio.gather(
            *(socket.send_json(message) for socket in targets),
            return_exceptions=True,
        )

        dead = [
            socket
            for socket, result in zip(targets, results, strict=True)
            if isinstance(result, BaseException)
        ]
        if dead:
            async with self._lock:
                self._connections.difference_update(dead)
            logger.info("dropped %d dead websocket(s)", len(dead))

    async def close_all(self) -> None:
        """Close every socket on shutdown so clients reconnect cleanly."""
        async with self._lock:
            targets = list(self._connections)
            self._connections.clear()

        await asyncio.gather(
            *(socket.close() for socket in targets), return_exceptions=True
        )


manager = ConnectionManager()
