"""The trained artifacts and the prediction contract the API depends on."""

from __future__ import annotations

import pytest

from app.ml.predictor import get_model
from app.ml.taxonomy import CATEGORIES, CONFIDENCE_REVIEW_THRESHOLD, URGENCIES


@pytest.fixture(scope="module")
def model():
    loaded = get_model()
    loaded.load()
    return loaded


def test_prediction_contract(model) -> None:
    result = model.predict("We were charged twice on invoice INV-20415 and need a refund.")

    for prediction, labels in ((result.category, CATEGORIES), (result.urgency, URGENCIES)):
        scores = [score.confidence for score in prediction.distribution]
        assert prediction.label in labels
        assert {score.label for score in prediction.distribution} == set(labels)
        assert scores == sorted(scores, reverse=True)
        assert sum(scores) == pytest.approx(1.0, abs=0.01)
        assert prediction.confidence == scores[0]

    assert result.latency_ms >= 0
    assert result.model_version


@pytest.mark.parametrize(
    ("text", "category"),
    [
        ("We were charged $1,204.50 twice on invoice INV-20415, please refund the duplicate.", "Billing"),
        ("I cannot log in, the password reset email never arrives and my account is locked.", "Login/Access"),
        ("It would be great if you could add dark mode to the dashboard at some point.", "Feature Request"),
    ],
)
def test_unambiguous_tickets_get_the_obvious_category(model, text: str, category: str) -> None:
    assert model.predict(text).category.label == category


def test_stated_impact_drives_urgency(model) -> None:
    outage = model.predict(
        "Our entire production environment is down and we are losing revenue every minute."
    )
    trivial = model.predict("A tiny cosmetic thing, no rush at all, purely a nice to have.")

    assert outage.urgency.label == "Critical"
    assert trivial.urgency.label == "Low"


def test_review_flag_follows_the_threshold(model) -> None:
    result = model.predict("Something seems off with the reports page.")
    for target, prediction in (("category", result.category), ("urgency", result.urgency)):
        expected = prediction.confidence < CONFIDENCE_REVIEW_THRESHOLD[target]
        assert prediction.needs_review is expected


def test_rationale_names_the_words_that_mattered(model) -> None:
    rationale = model.predict("Refund the duplicate charge on our invoice").category.rationale
    assert rationale
    assert any("invoice" in term.term or "refund" in term.term for term in rationale)


def test_metrics_artifact_has_what_the_dashboard_renders(model) -> None:
    metrics = model.metrics()
    for target in ("category", "urgency"):
        block = metrics["models"][target]
        size = len(block["labels"])
        assert 0 < block["accuracy"] <= 1
        assert block["accuracy"] > block["baseline_accuracy"]
        assert len(block["confusion_matrix"]) == size
        assert all(len(row) == size for row in block["confusion_matrix"])
        assert block["confidence_curve"]
    assert "adjacent_accuracy" in metrics["models"]["urgency"]
