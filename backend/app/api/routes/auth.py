"""Authentication routes."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentAgent, SessionDep
from app.config import settings
from app.core.security import create_access_token, verify_password
from app.db.models import Agent
from app.schemas.auth import AgentOut, LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, session: SessionDep) -> TokenResponse:
    """Exchange credentials for a JWT.

    A wrong email and a wrong password return the identical error. Saying
    "no such account" would turn this endpoint into a way to enumerate who
    has one.
    """
    agent = (
        await session.execute(select(Agent).where(Agent.email == payload.email.lower()))
    ).scalar_one_or_none()

    if agent is None or not verify_password(payload.password, agent.password_hash):
        # Hashing is deliberately slow, so returning early on an unknown email
        # makes "no such user" measurably faster than "wrong password". A
        # fixed delay flattens that timing channel.
        await asyncio.sleep(0.15)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return TokenResponse(
        access_token=create_access_token(str(agent.id), {"email": agent.email}),
        expires_in=settings.access_token_ttl_minutes * 60,
        agent=AgentOut.model_validate(agent),
    )


@router.get("/me", response_model=AgentOut)
async def me(agent: CurrentAgent) -> AgentOut:
    """Return the signed-in agent. Used by the frontend to validate a stored token."""
    return AgentOut.model_validate(agent)
