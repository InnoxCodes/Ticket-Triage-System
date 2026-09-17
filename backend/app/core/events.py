"""In-process WebSocket broadcast hub.

Why native FastAPI WebSockets rather than Socket.IO: the requirement is
one-way fan-out of small JSON events to browser clients. Socket.IO brings a
protocol layer, a server dependency and a client bundle to solve reconnection
and transport fallback — problems a small reconnecting client already handles
for this use case.

Why WebSockets rather than the 5–10s polling the brief also allowed: the
product claim is that tickets "arrive live". A poll makes that untrue for up
to ten seconds at a time, and on a Critical ticket that delay is the entire
feature. The frontend still falls back to polling if the socket drops, so the
board is never stale even when the socket is unavailable.

**Scaling limit, stated plainly:** this hub is per-process. Two workers means
a client connected to worker A never sees an event published on worker B.
Fixing it is a Redis pub/sub backplane, and until there is a reason to run
more than one worker, adding Redis would be infrastructure with no user.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from fastapi import WebSocket
from fastapi.encoders import jsonable_encoder

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
        # while register/disconnect handlers mutate it from other tasks.
        self._lock = asyncio.Lock()

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    async def register(self, websocket: WebSocket) -> None:
        """Start broadcasting to a socket that is already accepted and authenticated."""
        async with self._lock:
            self._connections.add(websocket)
        logger.info("websocket connected (%d live)", len(self._connections))

    async def disconnect(self, websocket: WebSocket) -> None:
        """Stop tracking a socket. Safe to call more than once."""
        async with self._lock:
            self._connections.discard(websocket)
        logger.info("websocket disconnected (%d live)", len(self._connections))

    async def broadcast(self, event: EventType, payload: dict[str, Any]) -> None:
        """Send one event to every live client. Never raises into the caller.

        The message is encoded exactly once, before any send. This ordering is
        a bug fix, not a micro-optimisation: payloads carry ``datetime``
        values, which plain ``json.dumps`` rejects. When that encoding happened
        inside each per-socket ``send_json``, the resulting TypeError was
        indistinguishable from a vanished peer, so every client was silently
        dropped as "dead" and the live feed delivered nothing. Encoding up
        front keeps the two failure modes apart: a bad payload is logged as
        the error it is, and only genuine send failures remove a socket.
        """
        async with self._lock:
            targets = list(self._connections)

        if not targets:
            return

        try:
            text = json.dumps(
                jsonable_encoder(
                    {"type": event.value, "timestamp": datetime.now(UTC), "data": payload}
                )
            )
        except (TypeError, ValueError):
            # The ticket is already committed; a broken event must not turn a
            # successful API request into a 500.
            logger.exception("could not encode %s event for broadcast", event.value)
            return

        results = await asyncio.gather(
            *(socket.send_text(text) for socket in targets),
            return_exceptions=True,
        )

        failures = [
            (socket, result)
            for socket, result in zip(targets, results, strict=True)
            if isinstance(result, BaseException)
        ]
        if failures:
            async with self._lock:
                self._connections.difference_update(socket for socket, _ in failures)
            logger.info(
                "dropped %d websocket(s) after failed send (%s)",
                len(failures),
                ", ".join(sorted({type(error).__name__ for _, error in failures})),
            )

    async def close_all(self) -> None:
        """Close every socket on shutdown so clients reconnect cleanly."""
        async with self._lock:
            targets = list(self._connections)
            self._connections.clear()

        await asyncio.gather(*(socket.close() for socket in targets), return_exceptions=True)


manager = ConnectionManager()
