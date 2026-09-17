"""Health and demo-control routes."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, select

from app.api.deps import CurrentAgent, SessionDep
from app.config import settings
from app.core.events import manager
from app.db.models import Ticket
from app.ml.predictor import get_model
from app.services.simulator import simulator

router = APIRouter(tags=["system"])


class HealthOut(BaseModel):
    status: str
    app: str
    environment: str
    model_loaded: bool
    model_version: str
    ticket_count: int
    websocket_clients: int
    simulator_running: bool


@router.get("/health", response_model=HealthOut)
async def health(session: SessionDep) -> HealthOut:
    """Liveness plus enough state to debug a deployment at a glance.

    Deliberately more than a bare 200: "is the app up" is rarely the real
    question. "Is the app up *and* did it find its model artifacts" is, and
    that failure mode is otherwise invisible until the first ticket is
    submitted.
    """
    model = get_model()
    count = int((await session.execute(select(func.count(Ticket.id)))).scalar_one())

    return HealthOut(
        status="ok",
        app=settings.app_name,
        environment=settings.environment,
        model_loaded=model.is_loaded,
        model_version=model.version,
        ticket_count=count,
        websocket_clients=manager.connection_count,
        simulator_running=simulator.is_running,
    )


class SimulatorStateOut(BaseModel):
    running: bool
    interval_seconds: float


@router.get("/simulator", response_model=SimulatorStateOut)
async def simulator_state() -> SimulatorStateOut:
    """Whether the demo ticket generator is currently running."""
    return SimulatorStateOut(
        running=simulator.is_running, interval_seconds=simulator.interval_seconds
    )


@router.post("/simulator/start", response_model=SimulatorStateOut)
async def start_simulator(_: CurrentAgent) -> SimulatorStateOut:
    """Start injecting synthetic tickets so the live feed has traffic."""
    await simulator.start()
    return SimulatorStateOut(
        running=simulator.is_running, interval_seconds=simulator.interval_seconds
    )


@router.post("/simulator/stop", response_model=SimulatorStateOut)
async def stop_simulator(_: CurrentAgent) -> SimulatorStateOut:
    """Stop the synthetic ticket generator."""
    await simulator.stop()
    return SimulatorStateOut(
        running=simulator.is_running, interval_seconds=simulator.interval_seconds
    )
