"""Shared FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import InvalidTokenError, decode_access_token
from app.db.models import Agent
from app.db.session import get_session

# auto_error=False so a missing header reaches the handler below and produces
# the same 401 shape as an invalid one. Letting the default fire returns a
# 403 for "no header" and a 401 for "bad header", which is a confusing
# distinction for a client to handle.
bearer_scheme = HTTPBearer(auto_error=False)

SessionDep = Annotated[AsyncSession, Depends(get_session)]
CredentialsDep = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]

UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_agent(
    session: SessionDep, credentials: CredentialsDep
) -> Agent:
    """Resolve the authenticated agent, or raise 401.

    The agent is re-read from the database on every request rather than
    trusted from the token body. A JWT is a bearer credential, not a cache:
    if an account is deleted its outstanding tokens must stop working
    immediately, and only a lookup gives that.
    """
    if credentials is None or not credentials.credentials:
        raise UNAUTHORIZED

    try:
        payload = decode_access_token(credentials.credentials)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    subject = payload.get("sub")
    if not subject:
        raise UNAUTHORIZED

    try:
        agent_id = int(subject)
    except (TypeError, ValueError) as exc:
        raise UNAUTHORIZED from exc

    agent = (
        await session.execute(select(Agent).where(Agent.id == agent_id))
    ).scalar_one_or_none()

    if agent is None:
        raise UNAUTHORIZED
    return agent


CurrentAgent = Annotated[Agent, Depends(get_current_agent)]
