"""Background task that injects tickets so the live feed has traffic.

A real-time dashboard is unconvincing when nothing arrives. This drops a fresh,
model-unseen ticket into the queue every few seconds while it is running, so
the WebSocket feed, the slide-in animation and the analytics charts all have
something to do during a demo.

Off by default and toggled from the dashboard — an unattended process quietly
writing rows forever is not a good default, and the tickets are indistinguishable
from real ones once written.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import random

from app.config import settings
from app.core.events import EventType, manager
from app.db.session import SessionLocal
from app.services import ticket_service
from app.services.demo_data import make_ticket

logger = logging.getLogger(__name__)


class TicketSimulator:
    """Periodically creates tickets until stopped."""

    def __init__(self, interval_seconds: float | None = None) -> None:
        self.interval_seconds = interval_seconds or settings.simulator_interval_seconds
        self._task: asyncio.Task[None] | None = None
        self._rng = random.Random()

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        """Begin injecting tickets. Idempotent."""
        if self.is_running:
            return
        self._task = asyncio.create_task(self._run())
        logger.info("ticket simulator started (every %.1fs)", self.interval_seconds)

    async def stop(self) -> None:
        """Stop injecting and wait for the task to unwind."""
        if self._task is None:
            return

        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None
        logger.info("ticket simulator stopped")

    async def _run(self) -> None:
        """Emit a ticket per interval, with jitter, until cancelled."""
        while True:
            # Jitter stops tickets arriving on a metronome, which reads as
            # obviously fake in the UI.
            delay = self.interval_seconds * self._rng.uniform(0.55, 1.45)
            await asyncio.sleep(delay)

            try:
                await self._emit_one()
            except asyncio.CancelledError:
                raise
            except Exception:
                # A failed injection must never kill the loop — the simulator
                # would silently stop and look like a broken feed.
                logger.exception("simulator failed to create a ticket")

    async def _emit_one(self) -> None:
        """Create and broadcast one ticket in its own session."""
        subject, body, email = make_ticket(self._rng)

        # Background tasks get their own session; the request-scoped
        # dependency is not available and sharing one across tasks is unsafe.
        async with SessionLocal() as session:
            ticket = await ticket_service.create_ticket(
                session, subject=subject, body=body, requester_email=email
            )
            payload = ticket_service.to_summary(ticket)

        await manager.broadcast(EventType.TICKET_CREATED, payload)


simulator = TicketSimulator()
