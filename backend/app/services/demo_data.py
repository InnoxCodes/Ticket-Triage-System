"""Realistic demo tickets for seeding and the live simulator.

Reuses the same compositional generator that built the training corpus, but
with a **time-derived seed**. That detail matters: seeding the demo from
``data/tickets.csv`` would be easier and would quietly stack the deck, because
the model has already seen every one of those strings and would report
implausibly high confidence on all of them. Generating fresh text means the
demo shows the confidence distribution the model actually produces on unseen
input, low-confidence review flags included.

This is the one place ``app/`` imports from ``ml/``. The alternative — a second
hand-written pool of demo strings — would be duplicated content that drifts
from the real generator. The training package is a few dozen kilobytes and is
copied into the container anyway, so retraining inside a running deployment
stays possible.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from ml.generate_dataset import (  # noqa: E402
    CATEGORY_PRIOR,
    IMPLICIT_URGENCY_RATE,
    LEAN_URGENCY_PRIOR,
    LEAN_WEIGHTS,
    MISSTATEMENT_RATE,
    compose_ticket_parts,
    shift_urgency,
    weighted_choice,
)
from ml.noise import add_noise  # noqa: E402
from ml.templates import CATEGORY_TEMPLATES  # noqa: E402

MAX_SUBJECT_LENGTH = 72

_REQUESTER_DOMAINS = [
    "northwind.co", "acmelogistics.com", "brightpath.io", "vertexlabs.dev",
    "harbourfinance.co.uk", "meridianhealth.org", "clearsky.app", "bytenest.io",
]
_REQUESTER_NAMES = [
    "priya.shah", "daniel.okafor", "mei.tanaka", "lucas.moreau", "sara.lindqvist",
    "tom.whitfield", "aisha.rahman", "diego.ramos", "nina.kovac", "james.arden",
]


def _subject_from_topic(topic: str) -> str:
    """Turn the ticket's clean topical core into a subject line.

    Taken from the core *before* noise is applied, because people type subject
    lines more carefully than bodies. Cutting subjects out of the noisy body
    instead produced lines like "What HAPPENS to our data ... Logged from our",
    where casing noise and a dropped full stop leaked into the most visible
    text on the board.
    """
    subject = topic.strip().rstrip(".")
    if len(subject) > MAX_SUBJECT_LENGTH:
        subject = subject[:MAX_SUBJECT_LENGTH].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return subject[:1].upper() + subject[1:]


def make_ticket(rng: random.Random) -> tuple[str, str, str]:
    """Generate one unseen ticket as ``(subject, body, requester_email)``."""
    category = weighted_choice(CATEGORY_PRIOR, rng)
    lean = weighted_choice(LEAN_WEIGHTS[category], rng)
    if not CATEGORY_TEMPLATES[category][lean]:
        lean = "neutral"

    urgency = weighted_choice(LEAN_URGENCY_PRIOR[lean], rng)
    if rng.random() < MISSTATEMENT_RATE:
        urgency = shift_urgency(urgency, rng)

    topic, text = compose_ticket_parts(
        category,
        urgency,
        lean,
        state_urgency=rng.random() >= IMPLICIT_URGENCY_RATE,
        rng=rng,
    )
    body = add_noise(text, rng)

    email = f"{rng.choice(_REQUESTER_NAMES)}@{rng.choice(_REQUESTER_DOMAINS)}"
    return _subject_from_topic(topic), body, email
