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
import re
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
    compose_ticket,
    shift_urgency,
    weighted_choice,
)
from ml.noise import add_noise  # noqa: E402
from ml.templates import CATEGORY_TEMPLATES  # noqa: E402

MAX_SUBJECT_LENGTH = 72

# Leading greetings, stripped before deriving a subject line.
_GREETING_RE = re.compile(
    r"^(hi|hello|hey|good morning|dear)\b[^,.!?]*[,.]?\s*", re.IGNORECASE
)

_REQUESTER_DOMAINS = [
    "northwind.co", "acmelogistics.com", "brightpath.io", "vertexlabs.dev",
    "harbourfinance.co.uk", "meridianhealth.org", "clearsky.app", "bytenest.io",
]
_REQUESTER_NAMES = [
    "priya.shah", "daniel.okafor", "mei.tanaka", "lucas.moreau", "sara.lindqvist",
    "tom.whitfield", "aisha.rahman", "diego.ramos", "nina.kovac", "james.arden",
]


def _derive_subject(body: str) -> str:
    """Build a plausible subject line from the body's opening clause.

    Real reporters write a subject that paraphrases their first sentence, so
    taking that clause and trimming it produces something that reads right and
    — importantly — is not identical to the body, which would make the
    subject+body concatenation the model scores artificially repetitive.
    """
    text = _GREETING_RE.sub("", body.strip())

    sentence = re.split(r"(?<=[.!?])\s+", text)[0].strip().rstrip(".!?")
    if not sentence:
        sentence = text[:MAX_SUBJECT_LENGTH]

    if len(sentence) > MAX_SUBJECT_LENGTH:
        cut = sentence[:MAX_SUBJECT_LENGTH].rsplit(" ", 1)[0]
        sentence = f"{cut}..."

    return sentence[:1].upper() + sentence[1:] if sentence else "Support request"


def make_ticket(rng: random.Random) -> tuple[str, str, str]:
    """Generate one unseen ticket as ``(subject, body, requester_email)``."""
    category = weighted_choice(CATEGORY_PRIOR, rng)
    lean = weighted_choice(LEAN_WEIGHTS[category], rng)
    if not CATEGORY_TEMPLATES[category][lean]:
        lean = "neutral"

    urgency = weighted_choice(LEAN_URGENCY_PRIOR[lean], rng)
    if rng.random() < MISSTATEMENT_RATE:
        urgency = shift_urgency(urgency, rng)

    body = add_noise(
        compose_ticket(
            category,
            urgency,
            lean,
            state_urgency=rng.random() >= IMPLICIT_URGENCY_RATE,
            rng=rng,
        ),
        rng,
    )

    email = f"{rng.choice(_REQUESTER_NAMES)}@{rng.choice(_REQUESTER_DOMAINS)}"
    return _derive_subject(body), body, email
