"""Runtime inference: load the trained pipelines and score a ticket.

Loading strategy is a lazy, process-wide singleton. The artifacts are a few
hundred kilobytes and deserialising them takes tens of milliseconds, which is
fine once at startup and absurd on every request. ``warm_up()`` is called from
the FastAPI lifespan hook so the first real request does not pay that cost.

The interesting part of this module is :func:`explain`. Because the classifier
is linear, the score for a class is literally the dot product of the ticket's
TF-IDF vector with that class's coefficient row:

    score(class) = bias + sum over terms of  tfidf(term) * coefficient(term, class)

Every term's contribution is therefore an independent, signed number that can
be read straight off. That gives a genuine per-ticket explanation — "this was
flagged Critical because of 'production', 'losing revenue' and 'immediately'"
— rather than the global feature importances most write-ups stop at. It is the
concrete reason this project uses a linear model: a transformer would score a
little higher and would need a separate attribution method (SHAP, integrated
gradients) to say anything at all about *why*.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from joblib import load
from sklearn.pipeline import Pipeline

from app.ml.taxonomy import CONFIDENCE_REVIEW_THRESHOLD

ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"
CATEGORY_MODEL_PATH = ARTIFACT_DIR / "category_model.joblib"
URGENCY_MODEL_PATH = ARTIFACT_DIR / "urgency_model.joblib"
METRICS_PATH = ARTIFACT_DIR / "metrics.json"

# Terms whose contribution is this small are noise in the explanation — they
# clutter the UI without changing the decision.
_MIN_CONTRIBUTION = 1e-4


class ModelNotTrainedError(RuntimeError):
    """Raised when the artifacts are missing and inference is impossible."""


@dataclass(frozen=True, slots=True)
class LabelScore:
    """One class and the probability assigned to it."""

    label: str
    confidence: float


@dataclass(frozen=True, slots=True)
class TokenContribution:
    """How much one term pushed the prediction toward the winning class."""

    term: str
    weight: float


@dataclass(frozen=True, slots=True)
class Prediction:
    """The winning label plus the full distribution and its rationale."""

    label: str
    confidence: float
    # True when the top probability falls below the target's review threshold.
    # A triage system does not have to answer every ticket; it has to answer
    # the ones it is sure about and hand the rest to a person. The UI badges
    # these so an agent knows where their attention is actually worth
    # something.
    needs_review: bool = False
    distribution: list[LabelScore] = field(default_factory=list)
    rationale: list[TokenContribution] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class TriageResult:
    """Everything the API needs from a single scoring pass."""

    category: Prediction
    urgency: Prediction
    model_version: str
    latency_ms: float


class TicketTriageModel:
    """Loads both pipelines once and scores tickets against them."""

    def __init__(self, artifact_dir: Path = ARTIFACT_DIR) -> None:
        self._artifact_dir = artifact_dir
        self._category: Pipeline | None = None
        self._urgency: Pipeline | None = None
        self._version: str = "unknown"

    # -- loading ----------------------------------------------------------

    @property
    def is_loaded(self) -> bool:
        return self._category is not None and self._urgency is not None

    def load(self) -> None:
        """Deserialise both pipelines. Idempotent."""
        if self.is_loaded:
            return

        category_path = self._artifact_dir / "category_model.joblib"
        urgency_path = self._artifact_dir / "urgency_model.joblib"

        missing = [p.name for p in (category_path, urgency_path) if not p.exists()]
        if missing:
            raise ModelNotTrainedError(
                f"Missing model artifacts: {', '.join(missing)}. "
                "Run: python -m ml.generate_dataset && python -m ml.train"
            )

        self._category = load(category_path)
        self._urgency = load(urgency_path)
        self._version = self._read_version()

    def _read_version(self) -> str:
        """Use the training timestamp as the model version.

        Tagging every prediction with this is what makes the override log
        useful later: when agents start disagreeing with the model more often,
        the first question is always "did the model change?", and without a
        version stamped on each row that question is unanswerable.
        """
        metrics_path = self._artifact_dir / "metrics.json"
        if not metrics_path.exists():
            return "unknown"
        try:
            payload = json.loads(metrics_path.read_text(encoding="utf-8"))
            return str(payload.get("generated_at", "unknown"))
        except (json.JSONDecodeError, OSError):
            return "unknown"

    @property
    def version(self) -> str:
        return self._version

    def metrics(self) -> dict[str, Any]:
        """The evaluation report produced by the last training run."""
        metrics_path = self._artifact_dir / "metrics.json"
        if not metrics_path.exists():
            raise ModelNotTrainedError(
                "metrics.json not found. Run: python -m ml.train"
            )
        return json.loads(metrics_path.read_text(encoding="utf-8"))

    # -- inference --------------------------------------------------------

    def predict(self, text: str) -> TriageResult:
        """Score one ticket for both targets."""
        if not self.is_loaded:
            self.load()

        started = time.perf_counter()
        category = self._predict_one(self._category, text, "category")  # type: ignore[arg-type]
        urgency = self._predict_one(self._urgency, text, "urgency")  # type: ignore[arg-type]
        elapsed_ms = (time.perf_counter() - started) * 1000

        return TriageResult(
            category=category,
            urgency=urgency,
            model_version=self._version,
            latency_ms=round(elapsed_ms, 3),
        )

    def _predict_one(self, pipeline: Pipeline, text: str, target: str) -> Prediction:
        """Run one pipeline and assemble the full prediction record."""
        probabilities = pipeline.predict_proba([text])[0]
        classes = [str(c) for c in pipeline.named_steps["clf"].classes_]

        ranked = sorted(
            (
                LabelScore(label, round(float(p), 4))
                for label, p in zip(classes, probabilities, strict=True)
            ),
            key=lambda s: s.confidence,
            reverse=True,
        )
        winner = ranked[0]
        threshold = CONFIDENCE_REVIEW_THRESHOLD.get(target, 0.5)

        return Prediction(
            label=winner.label,
            confidence=winner.confidence,
            needs_review=winner.confidence < threshold,
            distribution=ranked,
            rationale=explain(pipeline, text, winner.label),
        )


def explain(pipeline: Pipeline, text: str, label: str, top_n: int = 6) -> list[TokenContribution]:
    """Per-term contributions toward ``label`` for this specific ticket.

    Multiplies the ticket's TF-IDF values by the coefficient row for the
    predicted class. Only terms actually present in the text have a non-zero
    TF-IDF value, so the result is specific to this ticket rather than a
    global summary of the model.

    Returns the strongest *positive* contributors — the evidence for the
    decision. Negative contributors (evidence against) are dropped, because
    the UI question an agent is asking is "why did it say this", not "why did
    it not say something else".
    """
    vectoriser = pipeline.named_steps["tfidf"]
    classifier = pipeline.named_steps["clf"]

    classes = [str(c) for c in classifier.classes_]
    if label not in classes:
        return []

    vector = vectoriser.transform([text])
    if vector.nnz == 0:
        # Preprocessing stripped everything — an empty or stopword-only ticket.
        return []

    coefficients = classifier.coef_
    if coefficients.shape[0] == 1 and len(classes) == 2:
        coefficients = np.vstack([-coefficients[0], coefficients[0]])

    weights = coefficients[classes.index(label)]
    feature_names = vectoriser.get_feature_names_out()

    # Only iterate the non-zero entries. The vocabulary runs to thousands of
    # features while a ticket touches a few dozen, so this is the difference
    # between a dense scan and a handful of multiplications.
    row = vector.tocoo()
    contributions = [
        TokenContribution(str(feature_names[column]), round(float(value * weights[column]), 5))
        for column, value in zip(row.col, row.data, strict=True)
    ]

    positive = [c for c in contributions if c.weight > _MIN_CONTRIBUTION]
    positive.sort(key=lambda c: c.weight, reverse=True)
    return positive[:top_n]


# Process-wide singleton. FastAPI shares one instance across requests; the
# pipelines are stateless at predict time, so this is safe under concurrency.
_model = TicketTriageModel()


def get_model() -> TicketTriageModel:
    """Return the shared model instance."""
    return _model


def warm_up() -> None:
    """Force artifact loading at startup so the first request is not slow."""
    _model.load()
