"""Synthetic data generation: reproducibility and demo-data quality."""

from __future__ import annotations

import random

from app.services.demo_data import MAX_SUBJECT_LENGTH, make_ticket
from ml.generate_dataset import compose_ticket, compose_ticket_parts, generate


def test_generation_is_deterministic_for_a_seed() -> None:
    assert generate(60, seed=3) == generate(60, seed=3)


def test_compose_ticket_and_parts_agree_under_the_same_random_state() -> None:
    # Guards the refactor that split out compose_ticket_parts: the committed
    # training corpus is only reproducible if both paths draw identically.
    first, second = random.Random(11), random.Random(11)
    for state_urgency in (True, False) * 25:
        kwargs = {"category": "Billing", "urgency": "High", "lean": "neutral", "state_urgency": state_urgency}
        text = compose_ticket(**kwargs, rng=first)
        topic, parts_text = compose_ticket_parts(**kwargs, rng=second)

        assert text == parts_text
        assert topic.lower() in text.lower()


def test_demo_subjects_are_clean_single_line_summaries() -> None:
    rng = random.Random(5)
    for _ in range(150):
        subject, body, email = make_ticket(rng)

        assert 3 <= len(subject) <= MAX_SUBJECT_LENGTH + 1
        assert subject[:1] == subject[:1].upper()
        assert not subject.lower().startswith(("hi ", "hi,", "hello", "hey", "dear", "morning", "good morning"))
        assert "\n" not in subject
        # A ticket with no greeting, impact statement or sign-off is just its
        # topic, so the body is not guaranteed to be longer than the subject.
        assert body.strip()
        assert "@" in email
