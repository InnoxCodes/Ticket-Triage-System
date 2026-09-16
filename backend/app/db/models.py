"""SQLAlchemy ORM models.

Three tables. The shape worth explaining is the split between ``Ticket`` and
``Override``: the ticket carries the *current* category and urgency, while
every agent correction is also appended to its own row.

Storing only the current value would be simpler and would throw away the most
valuable data the product generates. Agent corrections are free, continuously
arriving ground truth from real users — they are what the next training run
should learn from, and the override *rate* is the only honest answer to "is
the model still any good on today's traffic?". The AI's original guess is kept
on the ticket alongside the corrected value precisely so that question stays
answerable.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.ml.taxonomy import Category, TicketStatus, Urgency


def utcnow() -> datetime:
    """Timezone-aware UTC now.

    Used instead of ``datetime.utcnow`` (deprecated, and returns a naive
    datetime that silently compares wrong against aware ones) and instead of
    a database-side default, so the same clock stamps every row regardless of
    which engine is underneath.
    """
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Agent(Base):
    """A support agent who can log in and work the queue."""

    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    overrides: Mapped[list[Override]] = relationship(back_populates="agent")


class Ticket(Base):
    """A support ticket and everything the model said about it."""

    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Human-facing reference (TKT-000123). Separate from the surrogate key so
    # the URL-visible identifier never leaks row counts.
    reference: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)

    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    requester_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # -- current values, after any agent correction ------------------------
    category: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    urgency: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=TicketStatus.OPEN, index=True
    )

    # -- what the model originally said ------------------------------------
    # Never mutated by an override. This is the reference point the whole
    # reliability story depends on.
    ai_category: Mapped[str] = mapped_column(String(40), nullable=False)
    ai_urgency: Mapped[str] = mapped_column(String(20), nullable=False)
    ai_category_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    ai_urgency_confidence: Mapped[float] = mapped_column(Float, nullable=False)

    # Full probability distributions and per-term contributions, as returned
    # by the predictor. JSON rather than extra tables: it is read as one blob
    # by exactly one screen and never queried by field, so normalising it
    # would buy nothing and cost six joins.
    ai_category_scores: Mapped[list] = mapped_column(JSON, default=list)
    ai_urgency_scores: Mapped[list] = mapped_column(JSON, default=list)
    ai_category_rationale: Mapped[list] = mapped_column(JSON, default=list)
    ai_urgency_rationale: Mapped[list] = mapped_column(JSON, default=list)

    ai_needs_review: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    model_version: Mapped[str] = mapped_column(String(64), default="unknown")
    inference_ms: Mapped[float] = mapped_column(Float, default=0.0)

    # -- workflow ----------------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    overrides: Mapped[list[Override]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan", order_by="Override.created_at"
    )

    __table_args__ = (
        # The dashboard's default view is "open tickets, most severe first,
        # newest first". Without this the Kanban board does a full scan on
        # every poll.
        Index("ix_tickets_status_created", "status", "created_at"),
        Index("ix_tickets_category_urgency", "category", "urgency"),
    )

    @property
    def was_overridden(self) -> bool:
        """True when the current labels differ from what the model predicted."""
        return self.category != self.ai_category or self.urgency != self.ai_urgency


class Override(Base):
    """One agent correction to a model prediction.

    Append-only. A ticket corrected twice produces two rows, so the sequence
    of corrections stays visible rather than being flattened to a final state.
    """

    __tablename__ = "overrides"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), index=True, nullable=False
    )
    agent_id: Mapped[int | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"), nullable=True
    )

    # "category" or "urgency" — which prediction was corrected.
    field: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    from_value: Mapped[str] = mapped_column(String(40), nullable=False)
    to_value: Mapped[str] = mapped_column(String(40), nullable=False)

    # The model's confidence in the value being overridden. Lets the analytics
    # answer the question that actually matters: are agents correcting the
    # predictions the model was unsure about (the system working as designed),
    # or the ones it was confident about (the model is wrong and does not know
    # it)? Those two look identical in a raw override count.
    model_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    model_version: Mapped[str] = mapped_column(String(64), default="unknown")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )

    ticket: Mapped[Ticket] = relationship(back_populates="overrides")
    agent: Mapped[Agent | None] = relationship(back_populates="overrides")


# Re-exported so callers can validate against the label space without reaching
# into the ML package.
__all__ = ["Agent", "Base", "Category", "Override", "Ticket", "TicketStatus", "Urgency", "utcnow"]
