"""Analytics response models.

The dashboard's analytics view is one request. Splitting it into six endpoints
would mean six round trips and six chances for the panels to disagree with
each other because they were computed moments apart.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class CountBucket(BaseModel):
    """A label and how many tickets carry it."""

    label: str
    count: int


class TimeBucket(BaseModel):
    """Ticket volume for one day, split by severity for a stacked chart."""

    date: str
    total: int
    critical: int
    high: int
    medium: int
    low: int


class OverrideStats(BaseModel):
    """How often agents disagree with the model, and where.

    This is the honest reliability metric. Offline accuracy is measured
    against a held-out set the model was tuned on; the override rate is
    measured against real agents looking at real tickets, and it keeps
    updating after deployment.

    ``low_confidence_share`` is the part that makes the raw rate readable: if
    most overrides land on predictions the model already flagged as uncertain,
    the system is behaving as designed. If they land on confident predictions,
    the model is wrong and does not know it — a much worse failure.
    """

    total_tickets: int
    overridden_tickets: int
    override_rate: float
    category_overrides: int
    urgency_overrides: int
    low_confidence_share: float
    avg_confidence_when_overridden: float
    avg_confidence_when_accepted: float
    by_field: list[CountBucket]
    recent: list[dict[str, Any]]


class ModelPerformance(BaseModel):
    """Offline evaluation from the last training run, plus live agreement."""

    generated_at: str
    dataset: dict[str, Any]
    environment: dict[str, Any]
    category: dict[str, Any]
    urgency: dict[str, Any]


class AnalyticsSummary(BaseModel):
    """Everything the analytics page renders, in one payload."""

    total_tickets: int
    open_tickets: int
    in_progress_tickets: int
    resolved_tickets: int
    needs_review_tickets: int
    critical_open: int
    sla_breached: int
    avg_resolution_minutes: float | None
    median_resolution_minutes: float | None
    avg_inference_ms: float
    volume_over_time: list[TimeBucket]
    by_category: list[CountBucket]
    by_urgency: list[CountBucket]
    by_status: list[CountBucket]
    overrides: OverrideStats
