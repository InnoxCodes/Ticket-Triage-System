"""Ticket business logic.

All ticket reads and writes go through here rather than living in the route
handlers. Two payoffs: the override-logging rule is enforced in exactly one
place (a route cannot forget it and quietly break the audit trail), and the
persistence calls are isolated behind functions, so replacing SQLite with
MongoDB later means rewriting this module and nothing else.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Agent, Override, Ticket, TicketStatus, utcnow
from app.ml.predictor import TriageResult, get_model
from app.ml.taxonomy import sla_minutes, urgency_rank

PREVIEW_LENGTH = 180


# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------


def classification_text(subject: str, body: str) -> str:
    """The text actually handed to the model.

    Subject and body are concatenated rather than scored separately. Subjects
    are short and often the clearest statement of the problem ("URGENT: cannot
    log in"), while bodies carry the detail; a model that saw only one would
    be throwing away the other. Concatenating means TF-IDF sees both, and the
    subject's terms naturally weigh more per-token because the field is short.
    """
    return f"{subject}. {body}"


async def create_ticket(
    session: AsyncSession,
    *,
    subject: str,
    body: str,
    requester_email: str | None = None,
    created_at: datetime | None = None,
) -> Ticket:
    """Classify and persist a new ticket.

    Classification happens inline, before the row is written, so a ticket can
    never exist in an unclassified state. It costs ~4ms, which is well inside
    the request budget — queueing it would add a broker, a worker, a retry
    policy and a "pending" UI state to save four milliseconds.
    """
    result: TriageResult = get_model().predict(classification_text(subject, body))

    ticket = Ticket(
        reference="pending",
        subject=subject,
        body=body,
        requester_email=requester_email,
        category=result.category.label,
        urgency=result.urgency.label,
        status=TicketStatus.OPEN,
        ai_category=result.category.label,
        ai_urgency=result.urgency.label,
        ai_category_confidence=result.category.confidence,
        ai_urgency_confidence=result.urgency.confidence,
        ai_category_scores=[asdict(s) for s in result.category.distribution],
        ai_urgency_scores=[asdict(s) for s in result.urgency.distribution],
        ai_category_rationale=[asdict(c) for c in result.category.rationale],
        ai_urgency_rationale=[asdict(c) for c in result.urgency.rationale],
        ai_needs_review=result.category.needs_review or result.urgency.needs_review,
        model_version=result.model_version,
        inference_ms=result.latency_ms,
    )
    if created_at is not None:
        ticket.created_at = created_at
        ticket.updated_at = created_at

    session.add(ticket)
    # Flush to get the autoincrement id, then derive the human reference from
    # it. Keeping the two separate means the public identifier is never a raw
    # row id, while still being collision-free without a lookup.
    await session.flush()
    ticket.reference = f"TKT-{ticket.id:06d}"

    await session.commit()
    # Load `overrides` explicitly, even though a brand-new ticket has none.
    # Under asyncio a lazy relationship access raises MissingGreenlet instead
    # of quietly issuing a query, so a caller serialising this into a detail
    # response would crash on an empty list it never asked for.
    await session.refresh(ticket, attribute_names=["overrides"])
    return ticket


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------


def _apply_filters(
    statement: Select,
    *,
    category: str | None,
    urgency: str | None,
    status: str | None,
    needs_review: bool | None,
    overridden: bool | None,
    search: str | None,
    created_after: datetime | None,
    created_before: datetime | None,
) -> Select:
    """Attach the query filters the dashboard exposes."""
    if category:
        statement = statement.where(Ticket.category == category)
    if urgency:
        statement = statement.where(Ticket.urgency == urgency)
    if status:
        statement = statement.where(Ticket.status == status)
    if needs_review is not None:
        statement = statement.where(Ticket.ai_needs_review == needs_review)
    if overridden is not None:
        disagrees = (Ticket.category != Ticket.ai_category) | (
            Ticket.urgency != Ticket.ai_urgency
        )
        statement = statement.where(disagrees if overridden else ~disagrees)
    if created_after:
        statement = statement.where(Ticket.created_at >= created_after)
    if created_before:
        statement = statement.where(Ticket.created_at <= created_before)
    if search:
        # Parameterised LIKE. The wildcards are added here rather than taken
        # from the client, so a user searching for "100%" cannot turn their
        # query into a match-everything scan.
        pattern = f"%{search.strip()}%"
        statement = statement.where(
            Ticket.subject.ilike(pattern)
            | Ticket.body.ilike(pattern)
            | Ticket.reference.ilike(pattern)
        )
    return statement


async def list_tickets(
    session: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 50,
    category: str | None = None,
    urgency: str | None = None,
    status: str | None = None,
    needs_review: bool | None = None,
    overridden: bool | None = None,
    search: str | None = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    sort: str = "newest",
) -> tuple[list[Ticket], int]:
    """Return one page of tickets plus the unpaginated total."""
    filters: dict[str, Any] = {
        "category": category,
        "urgency": urgency,
        "status": status,
        "needs_review": needs_review,
        "overridden": overridden,
        "search": search,
        "created_after": created_after,
        "created_before": created_before,
    }

    # Count over the same predicates but without ORDER BY or the eager load —
    # sorting a result set you are only going to count is wasted work.
    count_statement = _apply_filters(select(func.count(Ticket.id)), **filters)
    total = int((await session.execute(count_statement)).scalar_one())

    statement = _apply_filters(select(Ticket), **filters)
    statement = _apply_sort(statement, sort)
    statement = statement.offset((page - 1) * page_size).limit(page_size)

    rows = (await session.execute(statement)).scalars().all()
    return list(rows), total


def _apply_sort(statement: Select, sort: str) -> Select:
    """Order results. ``severity`` sorts by urgency rank, then recency."""
    if sort == "oldest":
        return statement.order_by(Ticket.created_at.asc())
    if sort == "severity":
        # Urgency is stored as text, so lexical ordering would give
        # Critical/High/Low/Medium. A CASE expression maps each label to its
        # ordinal rank and keeps the ordering meaningful in SQL.
        from sqlalchemy import case

        ranking = case(
            _urgency_ranks(),
            value=Ticket.urgency,
            else_=99,
        )
        return statement.order_by(ranking.asc(), Ticket.created_at.desc())
    return statement.order_by(Ticket.created_at.desc())


def _urgency_ranks() -> dict[str, int]:
    from app.ml.taxonomy import URGENCIES

    return {label: urgency_rank(label) for label in URGENCIES}


async def get_ticket(session: AsyncSession, ticket_id: int) -> Ticket | None:
    """Fetch one ticket with its override history eagerly loaded."""
    statement = (
        select(Ticket)
        .where(Ticket.id == ticket_id)
        # selectinload, not lazy loading: a lazy relationship access under
        # asyncio raises MissingGreenlet rather than quietly doing an extra
        # query, so eager loading here is required, not just an optimisation.
        .options(selectinload(Ticket.overrides).selectinload(Override.agent))
    )
    return (await session.execute(statement)).scalar_one_or_none()


# ---------------------------------------------------------------------------
# Updating
# ---------------------------------------------------------------------------


async def update_ticket(
    session: AsyncSession,
    ticket: Ticket,
    *,
    status: str | None = None,
    category: str | None = None,
    urgency: str | None = None,
    agent: Agent | None = None,
) -> tuple[Ticket, list[Override]]:
    """Apply an agent's changes, logging any prediction override.

    Returns the ticket and the override rows created, so the caller can
    broadcast a distinct event when a correction happened rather than a
    generic update.
    """
    logged: list[Override] = []

    if category is not None and category != ticket.category:
        logged.append(
            _log_override(
                ticket,
                agent,
                field="category",
                from_value=ticket.category,
                to_value=category,
                # Confidence in the value being *replaced*, which is the
                # number that says whether the model should have known better.
                confidence=ticket.ai_category_confidence,
            )
        )
        ticket.category = category

    if urgency is not None and urgency != ticket.urgency:
        logged.append(
            _log_override(
                ticket,
                agent,
                field="urgency",
                from_value=ticket.urgency,
                to_value=urgency,
                confidence=ticket.ai_urgency_confidence,
            )
        )
        ticket.urgency = urgency

    if status is not None and status != ticket.status:
        ticket.status = status
        # Stamp on the transition into Resolved and clear it on the way back
        # out, otherwise a reopened ticket keeps a resolution timestamp and
        # silently corrupts the average-resolution-time metric.
        ticket.resolved_at = utcnow() if status == TicketStatus.RESOLVED else None

    ticket.updated_at = utcnow()

    for override in logged:
        session.add(override)

    await session.commit()
    await session.refresh(ticket)
    return ticket, logged


def _log_override(
    ticket: Ticket,
    agent: Agent | None,
    *,
    field: str,
    from_value: str,
    to_value: str,
    confidence: float,
) -> Override:
    """Build an override record. Never mutates the ai_* columns."""
    return Override(
        ticket_id=ticket.id,
        agent_id=agent.id if agent else None,
        field=field,
        from_value=from_value,
        to_value=to_value,
        model_confidence=confidence,
        model_version=ticket.model_version,
    )


async def delete_ticket(session: AsyncSession, ticket: Ticket) -> None:
    """Remove a ticket and, by cascade, its overrides."""
    await session.delete(ticket)
    await session.commit()


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------


def _as_aware(value: datetime) -> datetime:
    """Attach UTC to a naive datetime.

    SQLite has no native timestamp type: SQLAlchemy stores an ISO string and
    reads it back without a tzinfo even when the column is declared
    ``timezone=True``. Comparing that against an aware ``now()`` raises. This
    normalises on the way out so the SLA arithmetic below is safe on both
    SQLite and Postgres.
    """
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def sla_state(ticket: Ticket) -> tuple[int, bool]:
    """Target response minutes for this ticket, and whether it has blown it.

    A resolved ticket is judged against when it was resolved; an open one
    against now. Judging a resolved ticket against the current clock would
    make historical breaches grow forever.
    """
    target = sla_minutes(ticket.urgency)
    reference = _as_aware(ticket.resolved_at) if ticket.resolved_at else datetime.now(UTC)
    deadline = _as_aware(ticket.created_at) + timedelta(minutes=target)
    return target, reference > deadline


def to_summary(ticket: Ticket) -> dict[str, Any]:
    """The compact card shape, without body or model internals."""
    target, breached = sla_state(ticket)
    body = ticket.body.strip()
    preview = body if len(body) <= PREVIEW_LENGTH else body[:PREVIEW_LENGTH].rstrip() + "..."

    return {
        "id": ticket.id,
        "reference": ticket.reference,
        "subject": ticket.subject,
        "preview": preview,
        "category": ticket.category,
        "urgency": ticket.urgency,
        "status": ticket.status,
        "ai_category": ticket.ai_category,
        "ai_urgency": ticket.ai_urgency,
        "ai_category_confidence": ticket.ai_category_confidence,
        "ai_urgency_confidence": ticket.ai_urgency_confidence,
        "ai_needs_review": ticket.ai_needs_review,
        "was_overridden": ticket.was_overridden,
        "created_at": _as_aware(ticket.created_at),
        "updated_at": _as_aware(ticket.updated_at),
        "resolved_at": _as_aware(ticket.resolved_at) if ticket.resolved_at else None,
        "sla_minutes": target,
        "sla_breached": breached,
    }


def to_detail(ticket: Ticket) -> dict[str, Any]:
    """The full record, including both distributions and the audit trail."""
    payload = to_summary(ticket)
    payload.update(
        {
            "body": ticket.body,
            "requester_email": ticket.requester_email,
            "ai_category_scores": ticket.ai_category_scores or [],
            "ai_urgency_scores": ticket.ai_urgency_scores or [],
            "ai_category_rationale": ticket.ai_category_rationale or [],
            "ai_urgency_rationale": ticket.ai_urgency_rationale or [],
            "model_version": ticket.model_version,
            "inference_ms": ticket.inference_ms,
            "overrides": [
                {
                    "id": o.id,
                    "field": o.field,
                    "from_value": o.from_value,
                    "to_value": o.to_value,
                    "model_confidence": o.model_confidence,
                    "created_at": _as_aware(o.created_at),
                    "agent_name": o.agent.name if o.agent else None,
                }
                for o in ticket.overrides
            ],
        }
    )
    return payload
