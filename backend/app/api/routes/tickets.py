"""Ticket CRUD, classification preview, and the label taxonomy."""

from __future__ import annotations

import math
from dataclasses import asdict
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.api.deps import CurrentAgent, SessionDep
from app.core.events import EventType, manager
from app.ml.predictor import ModelNotTrainedError, get_model
from app.schemas.ticket import (
    PredictionPreview,
    TaxonomyOut,
    TicketCreate,
    TicketDetail,
    TicketPage,
    TicketSummary,
    TicketUpdate,
)
from app.services import ticket_service

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.get("/taxonomy", response_model=TaxonomyOut)
async def taxonomy() -> TaxonomyOut:
    """The valid label values.

    Served rather than duplicated in the frontend so adding a category is a
    one-place change instead of a hunt for hardcoded string arrays.
    """
    return TaxonomyOut()


@router.post("/classify", response_model=PredictionPreview)
async def classify(payload: TicketCreate) -> PredictionPreview:
    """Score a ticket without saving it.

    Powers the submission form's "Analysing..." step, so a customer sees what
    the model thinks before committing. Deliberately unauthenticated and
    side-effect free — it is the public-facing half of the product.
    """
    try:
        result = get_model().predict(
            ticket_service.classification_text(payload.subject, payload.body)
        )
    except ModelNotTrainedError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    return PredictionPreview(
        category=result.category.label,
        category_confidence=result.category.confidence,
        category_scores=[asdict(s) for s in result.category.distribution],
        category_rationale=[asdict(c) for c in result.category.rationale],
        category_needs_review=result.category.needs_review,
        urgency=result.urgency.label,
        urgency_confidence=result.urgency.confidence,
        urgency_scores=[asdict(s) for s in result.urgency.distribution],
        urgency_rationale=[asdict(c) for c in result.urgency.rationale],
        urgency_needs_review=result.urgency.needs_review,
        model_version=result.model_version,
        inference_ms=result.latency_ms,
    )


@router.post("", response_model=TicketDetail, status_code=status.HTTP_201_CREATED)
async def create_ticket(payload: TicketCreate, session: SessionDep) -> TicketDetail:
    """Submit a ticket. Classifies inline, stores, then broadcasts.

    Unauthenticated by design: this is the customer's entry point. The agent
    dashboard behind it is what requires a token.
    """
    try:
        ticket = await ticket_service.create_ticket(
            session,
            subject=payload.subject,
            body=payload.body,
            requester_email=payload.requester_email,
        )
    except ModelNotTrainedError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    detail = ticket_service.to_detail(ticket)

    # Broadcast the summary rather than the detail: the board only renders
    # card fields, and pushing both distributions to every connected client
    # on every ticket would be most of the payload for none of the pixels.
    await manager.broadcast(EventType.TICKET_CREATED, ticket_service.to_summary(ticket))

    return TicketDetail.model_validate(detail)


@router.get("", response_model=TicketPage)
async def list_tickets(
    session: SessionDep,
    _: CurrentAgent,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 100,
    category: str | None = None,
    urgency: str | None = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    needs_review: bool | None = None,
    overridden: bool | None = None,
    search: Annotated[str | None, Query(max_length=200)] = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    sort: Annotated[str, Query(pattern="^(newest|oldest|severity)$")] = "newest",
) -> TicketPage:
    """List tickets with filtering, sorting and pagination."""
    items, total = await ticket_service.list_tickets(
        session,
        page=page,
        page_size=page_size,
        category=category,
        urgency=urgency,
        status=status_filter,
        needs_review=needs_review,
        overridden=overridden,
        search=search,
        created_after=created_after,
        created_before=created_before,
        sort=sort,
    )

    return TicketPage(
        items=[TicketSummary.model_validate(ticket_service.to_summary(t)) for t in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, math.ceil(total / page_size)),
    )


@router.get("/{ticket_id}", response_model=TicketDetail)
async def get_ticket(ticket_id: int, session: SessionDep, _: CurrentAgent) -> TicketDetail:
    """Full ticket detail, including the model's confidence breakdown. Agent-only.

    Reads are gated as well as writes: the body and requester email are
    customer data, and an unauthenticated GET would expose every ticket to
    anyone who can count upward from id 1.
    """
    ticket = await ticket_service.get_ticket(session, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return TicketDetail.model_validate(ticket_service.to_detail(ticket))


@router.patch("/{ticket_id}", response_model=TicketDetail)
async def update_ticket(
    ticket_id: int, payload: TicketUpdate, session: SessionDep, agent: CurrentAgent
) -> TicketDetail:
    """Move a ticket's status, or override the model. Requires authentication.

    Any change to category or urgency is logged as an override against the
    signed-in agent — that audit trail is the product's live reliability
    signal, so the mutation is gated on knowing who made it.
    """
    if not payload.has_changes():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide at least one of: status, category, urgency",
        )

    ticket = await ticket_service.get_ticket(session, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    ticket, overrides = await ticket_service.update_ticket(
        session,
        ticket,
        status=payload.status,
        category=payload.category,
        urgency=payload.urgency,
        agent=agent,
    )

    # Re-read so the response carries the newly written override rows.
    refreshed = await ticket_service.get_ticket(session, ticket_id)
    assert refreshed is not None

    summary = ticket_service.to_summary(refreshed)
    event = EventType.TICKET_OVERRIDDEN if overrides else EventType.TICKET_UPDATED
    await manager.broadcast(event, summary)

    return TicketDetail.model_validate(ticket_service.to_detail(refreshed))


@router.delete(
    "/{ticket_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    # Both are required. FastAPI infers the response model from the return
    # annotation, and `-> None` yields the *class* NoneType, which is truthy —
    # so it builds a response field and then asserts, because 204 forbids a
    # body. Passing response_model=None explicitly is the documented opt-out.
    response_model=None,
    response_class=Response,
)
async def delete_ticket(ticket_id: int, session: SessionDep, agent: CurrentAgent) -> None:
    """Delete a ticket and its override history."""
    ticket = await ticket_service.get_ticket(session, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    await ticket_service.delete_ticket(session, ticket)
    await manager.broadcast(EventType.STATS_INVALIDATED, {"deleted_id": ticket_id})
