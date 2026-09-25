"""The cleaning pipeline shared by training and inference."""

from __future__ import annotations

import pytest

from app.ml.preprocess import expand_contractions, mask_entities, preprocess


def test_negations_survive_so_opposite_tickets_stay_distinguishable() -> None:
    broken = preprocess("I cannot log in at all and nothing works")
    fine = preprocess("I can log in and everything works fine")

    assert "cannot" in broken.split()
    assert "nothing" in broken.split()
    assert broken != fine


@pytest.mark.parametrize(
    ("raw", "token"),
    [
        ("charged $4,812.00 twice", "moneyamt"),
        ("see invoice INV-99213", "refnum"),
        ("email me at ops@acme.io", "emailaddr"),
        ("fails at https://api.acme.io/v2/orders", "urladdr"),
        ("blocked from 192.168.0.14", "ipaddr"),
        ("since 2026-08-14", "datestr"),
    ],
)
def test_high_cardinality_literals_are_masked(raw: str, token: str) -> None:
    assert token in preprocess(raw).split()


def test_short_numbers_that_carry_meaning_are_kept() -> None:
    assert "500" in preprocess("the API returns a 500 error").split()
    assert "longnum" in mask_entities("order 84720193")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("can't see it", "cannot see it"),
        ("won't load", "will not load"),
        ("it wasn't there", "it was not there"),
        ("dont know", "do not know"),
    ],
)
def test_contractions_expand_to_explicit_negation(raw: str, expected: str) -> None:
    assert expand_contractions(raw) == expected


def test_bare_contraction_rules_do_not_rewrite_inside_words() -> None:
    # "im" must not fire inside "immediately", nor "ive" inside "five".
    assert expand_contractions("immediately five video") == "immediately five video"


def test_severity_slang_is_normalised() -> None:
    tokens = preprocess("need this fixed asap").split()
    assert "urgent" in tokens
    assert "immediately" in tokens


def test_contentless_words_are_dropped_and_emphasis_is_normalised() -> None:
    assert preprocess("Hi team, THE dashboard is BROKEN!!!!") == "dashboard broken"


def test_empty_input_is_safe() -> None:
    assert preprocess("") == ""
