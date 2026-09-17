"""FastAPI application factory and lifespan wiring."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import analytics, auth, system, tickets, ws
from app.config import settings
from app.core.events import manager
from app.db.session import dispose_db, init_db
from app.ml.predictor import ModelNotTrainedError, warm_up
from app.services.simulator import simulator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("triageai")

DESCRIPTION = """
Automatic triage for inbound support tickets.

Every ticket is classified on submission into a **category** (what it is about)
and an **urgency** (how fast it needs a human), with a calibrated confidence
score for each. Predictions below the confidence threshold are flagged for
human review rather than routed silently.

* `POST /api/tickets/classify` — score without saving (the form preview)
* `POST /api/tickets` — submit, classify and store
* `PATCH /api/tickets/{id}` — move status, or override the model (logged)
* `GET  /api/analytics/summary` — volume, distributions, override reliability
* `WS   /ws/tickets` — live event feed

Agent endpoints require a bearer token from `POST /api/auth/login`.
"""


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
    """Start-up and shut-down sequence."""
    settings.validate_for_runtime()
    await init_db()

    # Load the model eagerly. A missing artifact is logged as a warning rather
    # than crashing the process: the API stays useful for reading existing
    # tickets and the /health endpoint reports model_loaded=false, which is a
    # far better failure mode than a container that will not boot.
    try:
        warm_up()
        logger.info("model artifacts loaded")
    except ModelNotTrainedError as exc:
        logger.warning("%s", exc)

    await _seed_agent()

    logger.info("%s ready (%s)", settings.app_name, settings.environment)
    yield

    await simulator.stop()
    await manager.close_all()
    await dispose_db()


async def _seed_agent() -> None:
    """Create the demo agent if it does not exist yet.

    Runs on every boot so a fresh clone has working login credentials without
    a separate setup command. Idempotent — an existing account is left alone,
    including its password, so a changed one is not silently reset.
    """
    from sqlalchemy import select

    from app.core.security import hash_password
    from app.db.models import Agent
    from app.db.session import SessionLocal

    async with SessionLocal() as session:
        existing = (
            await session.execute(
                select(Agent).where(Agent.email == settings.seed_agent_email)
            )
        ).scalar_one_or_none()

        if existing is not None:
            return

        session.add(
            Agent(
                email=settings.seed_agent_email,
                name=settings.seed_agent_name,
                password_hash=hash_password(settings.seed_agent_password),
            )
        )
        await session.commit()
        logger.info("seeded demo agent %s", settings.seed_agent_email)


def create_app() -> FastAPI:
    """Build the application. A factory so tests can construct isolated copies."""
    app = FastAPI(
        title=settings.app_name,
        description=DESCRIPTION,
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        """Flatten Pydantic's nested errors into something a UI can display.

        The default 422 body nests field paths inside a ``loc`` array that a
        frontend has to walk to render a message next to the right input.
        This maps each error to ``field`` + ``message`` so the form can bind
        them directly.
        """
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": "Validation failed",
                "errors": [
                    {
                        "field": ".".join(str(p) for p in error["loc"][1:]) or "body",
                        "message": error["msg"],
                    }
                    for error in exc.errors()
                ],
            },
        )

    # Everything REST lives under /api; the WebSocket sits at the root so its
    # URL reads as a protocol endpoint rather than a resource.
    app.include_router(system.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(tickets.router, prefix="/api")
    app.include_router(analytics.router, prefix="/api")
    app.include_router(ws.router)

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {
            "app": settings.app_name,
            "docs": "/docs",
            "health": "/api/health",
        }

    return app


app = create_app()
