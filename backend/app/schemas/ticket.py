"""Pydantic request/response models for tickets.

These are the API contract. They are kept separate from the ORM models on
purpose: the database row carries fields no client should see or set
(``ai_category`` must never be writable, or the override audit trail becomes
fiction), and the response shape is organised for the UI rather than for
storage.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.ml.taxonomy import CATEGORIES, STATUSES, URGENCIES

CategoryLiteral = Literal[
    "Billing", "Bug Report", "Login/Access", "Feature Request",
    "General Inquiry", "Technical Issue",
]
UrgencyLiteral = Literal["Critical", "High", "Medium", "Low"]
StatusLiteral = Literal["Open", "In Progress", "Resolved"]


class LabelScoreOut(BaseModel):
    """One class and its probability, for the confidence bars."""

    label: str
    confidence: float


class TokenContributionOut(BaseModel):
    """One term and how much it pushed the prediction."""

    term: str
    weight: float


class TicketCreate(BaseModel):
    """Payload for submitting a ticket from the customer-facing form."""

    subject: Annotated[str, Field(min_length=3, max_length=200)]
    body: Annotated[str, Field(min_length=10, max_length=5000)]
    requester_email: EmailStr | None = None

    @field_validator("subject", "body")
    @classmethod
    def not_blank(cls, value: str) -> str:
        """Reject whitespace-only input that would pass a min_length check."""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("must not be blank")
        return cleaned


class TicketUpdate(BaseModel):
    """Agent-initiated changes: move status, or override a prediction.

    All fields optional — this is a PATCH. Sending an empty body is rejected
    by the route rather than silently succeeding, so a broken client surfaces
    as a 400 instead of a no-op the user thinks worked.
    """

    status: StatusLiteral | None = None
    category: CategoryLiteral | None = None
    urgency: UrgencyLiteral | None = None

    def has_changes(self) -> bool:
        return any(v is not None for v in (self.status, self.category, self.urgency))


class OverrideOut(BaseModel):
    """One logged agent correction."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    field: str
    from_value: str
    to_value: str
    model_confidence: float
    created_at: datetime
    agent_name: str | None = None


class TicketSummary(BaseModel):
    """The compact shape rendered on a Kanban card.

    Deliberately excludes the body, both probability distributions and both
    rationales. A board showing 200 cards would otherwise ship several hundred
    kilobytes of JSON the user cannot see, on every poll. The detail panel
    fetches the full record for the one ticket that is actually open.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    reference: str
    subject: str
    preview: str
    category: str
    urgency: str
    status: str
    ai_category: str
    ai_urgency: str
    ai_category_confidence: float
    ai_urgency_confidence: float
    ai_needs_review: bool
    was_overridden: bool
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    sla_minutes: int
    sla_breached: bool


class TicketDetail(TicketSummary):
    """Everything about one ticket, including the model's full reasoning."""

    body: str
    requester_email: str | None
    ai_category_scores: list[LabelScoreOut]
    ai_urgency_scores: list[LabelScoreOut]
    ai_category_rationale: list[TokenContributionOut]
    ai_urgency_rationale: list[TokenContributionOut]
    model_version: str
    inference_ms: float
    overrides: list[OverrideOut]


class TicketPage(BaseModel):
    """One page of results plus the totals the UI needs for pagination."""

    items: list[TicketSummary]
    total: int
    page: int
    page_size: int
    pages: int


class PredictionPreview(BaseModel):
    """Classification without persistence, for the form's 'Analysing...' step."""

    category: str
    category_confidence: float
    category_scores: list[LabelScoreOut]
    category_rationale: list[TokenContributionOut]
    category_needs_review: bool
    urgency: str
    urgency_confidence: float
    urgency_scores: list[LabelScoreOut]
    urgency_rationale: list[TokenContributionOut]
    urgency_needs_review: bool
    model_version: str
    inference_ms: float


class TaxonomyOut(BaseModel):
    """The label space, so the frontend never hardcodes its own copy."""

    categories: list[str] = Field(default_factory=lambda: list(CATEGORIES))
    urgencies: list[str] = Field(default_factory=lambda: list(URGENCIES))
    statuses: list[str] = Field(default_factory=lambda: list(STATUSES))
