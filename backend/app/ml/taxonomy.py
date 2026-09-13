"""Canonical label space for TriageAI.

This module is the single source of truth for the two things the models
predict. The dataset generator, the training scripts, the API schemas and the
frontend type definitions all trace back to the constants defined here, so a
label can never drift out of sync between the model and the database.

Two independent label sets are predicted from the same ticket text:

  * CATEGORY — *what the ticket is about* (a topic/domain judgement)
  * URGENCY  — *how fast it needs a human* (an impact/severity judgement)

Keeping them separate matters. A billing ticket can be trivial ("what's my
invoice number?") or existential ("we were double-charged $40k and the board
meeting is in an hour"). A single 24-class "category x urgency" model would
have to learn every combination independently and would starve the rare cells
of training data. Two focused classifiers share the same text but learn from
completely different vocabulary, and each one gets the full dataset.
"""

from __future__ import annotations

from enum import StrEnum


class Category(StrEnum):
    """What the ticket is about."""

    BILLING = "Billing"
    BUG_REPORT = "Bug Report"
    LOGIN_ACCESS = "Login/Access"
    FEATURE_REQUEST = "Feature Request"
    GENERAL_INQUIRY = "General Inquiry"
    TECHNICAL_ISSUE = "Technical Issue"


class Urgency(StrEnum):
    """How quickly the ticket needs a human."""

    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class TicketStatus(StrEnum):
    """Where the ticket sits in the agent workflow (the Kanban columns)."""

    OPEN = "Open"
    IN_PROGRESS = "In Progress"
    RESOLVED = "Resolved"


# Explicit orderings. `list(Category)` would also work, but pinning the order
# here guarantees that confusion-matrix axes, API responses and chart legends
# all agree — silently reordering these would scramble the saved metrics.
CATEGORIES: list[str] = [c.value for c in Category]
URGENCIES: list[str] = [u.value for u in Urgency]
STATUSES: list[str] = [s.value for s in TicketStatus]

# Urgency is ordinal, unlike category. Exposing a numeric rank lets the API
# sort a queue by "most severe first" without hardcoding the order in SQL, and
# lets the evaluation step report how *far off* a misprediction was — calling a
# Critical ticket "High" is a much cheaper mistake than calling it "Low".
URGENCY_RANK: dict[str, int] = {
    Urgency.CRITICAL: 0,
    Urgency.HIGH: 1,
    Urgency.MEDIUM: 2,
    Urgency.LOW: 3,
}

# Target response times per urgency level. Not used by the model at all — this
# is business policy, surfaced in the UI as an SLA countdown on each card.
SLA_MINUTES: dict[str, int] = {
    Urgency.CRITICAL: 30,
    Urgency.HIGH: 4 * 60,
    Urgency.MEDIUM: 24 * 60,
    Urgency.LOW: 72 * 60,
}


def urgency_rank(urgency: str) -> int:
    """Return the ordinal severity of ``urgency`` (0 = most severe)."""
    return URGENCY_RANK[Urgency(urgency)]


def sla_minutes(urgency: str) -> int:
    """Return the target first-response time in minutes for ``urgency``."""
    return SLA_MINUTES[Urgency(urgency)]
