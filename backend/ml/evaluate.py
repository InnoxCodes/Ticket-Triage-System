"""Model evaluation: metrics, confusion matrices and feature interpretability.

Split out from ``train.py`` so the metric computation is importable and
testable on its own, and so the exact same code path produces both the
terminal report and the JSON the API serves to the dashboard's "model
performance" panel. The number quoted in the UI is therefore provably the
number the model actually scored — there is no second, hand-copied figure to
drift out of date.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.pipeline import Pipeline

from app.ml.taxonomy import URGENCY_RANK


def per_class_metrics(
    y_true: list[str], y_pred: list[str], labels: list[str]
) -> list[dict[str, Any]]:
    """Precision / recall / F1 / support for each label, in canonical order."""
    report = classification_report(
        y_true, y_pred, labels=labels, output_dict=True, zero_division=0
    )
    return [
        {
            "label": label,
            "precision": round(report[label]["precision"], 4),
            "recall": round(report[label]["recall"], 4),
            "f1": round(report[label]["f1-score"], 4),
            "support": int(report[label]["support"]),
        }
        for label in labels
    ]


def confusion(y_true: list[str], y_pred: list[str], labels: list[str]) -> list[list[int]]:
    """Confusion matrix as plain nested lists, rows = true, cols = predicted."""
    return confusion_matrix(y_true, y_pred, labels=labels).tolist()


def adjacent_accuracy(y_true: list[str], y_pred: list[str]) -> float:
    """Share of urgency predictions that are within one severity level.

    Urgency is ordinal, so a flat accuracy score throws away information:
    predicting "High" for a Critical ticket is a near miss that still puts the
    ticket near the top of the queue, while predicting "Low" is a genuine
    triage failure. This metric is what tells you whether the errors are
    clustered on the diagonal or scattered — and it is the honest way to
    present a model whose raw accuracy looks middling.

    Not meaningful for category, which is nominal.
    """
    if not y_true:
        return 0.0
    within_one = sum(
        abs(URGENCY_RANK[t] - URGENCY_RANK[p]) <= 1 for t, p in zip(y_true, y_pred, strict=True)
    )
    return round(within_one / len(y_true), 4)


def top_features(pipeline: Pipeline, top_n: int = 8) -> dict[str, list[tuple[str, float]]]:
    """Highest-weighted n-grams driving each class.

    This is the payoff for choosing a linear model. Every prediction decomposes
    into a sum of per-token contributions, so the vocabulary the model actually
    relies on can be read straight off the coefficient matrix. The UI surfaces
    this, which turns "the AI said Critical" into "the AI said Critical because
    of 'production down' and 'losing revenue'" — the difference between a
    support agent trusting the tool and ignoring it.

    A transformer would score a point or two higher here and offer nothing
    remotely this legible without a separate attribution pass.
    """
    vectoriser = pipeline.named_steps["tfidf"]
    classifier = pipeline.named_steps["clf"]

    feature_names = np.asarray(vectoriser.get_feature_names_out())
    coefficients = classifier.coef_
    classes = list(classifier.classes_)

    # Binary logistic regression stores a single coefficient row describing the
    # positive class; mirror it so both classes render consistently.
    if coefficients.shape[0] == 1 and len(classes) == 2:
        coefficients = np.vstack([-coefficients[0], coefficients[0]])

    result: dict[str, list[tuple[str, float]]] = {}
    for index, label in enumerate(classes):
        weights = coefficients[index]
        top_indices = np.argsort(weights)[::-1][:top_n]
        result[str(label)] = [
            (str(feature_names[i]), round(float(weights[i]), 4)) for i in top_indices
        ]
    return result


def slice_metrics(
    y_true: list[str],
    y_pred: list[str],
    slices: dict[str, list[bool]],
) -> list[dict[str, Any]]:
    """Accuracy on named subsets of the held-out set.

    A single headline accuracy hides *where* a model fails, and for this
    project the where is the whole point. The urgency classifier scores around
    0.73 overall, but that one number is the average of two very different
    populations: tickets where the reporter stated their impact, and tickets
    where they did not. Splitting them turns "the model is mediocre" into "the
    model is strong when there is evidence and correctly falls back to the
    prior when there is none" — which is both true and actionable, since it
    says the fix is to ask reporters for impact, not to buy a bigger model.
    """
    results: list[dict[str, Any]] = []

    for name, mask in slices.items():
        subset_true = [t for t, keep in zip(y_true, mask, strict=True) if keep]
        subset_pred = [p for p, keep in zip(y_pred, mask, strict=True) if keep]

        if not subset_true:
            continue

        results.append(
            {
                "name": name,
                "n": len(subset_true),
                "accuracy": round(accuracy_score(subset_true, subset_pred), 4),
            }
        )

    return results


def evaluate_model(
    pipeline: Pipeline,
    x_test: list[str],
    y_test: list[str],
    labels: list[str],
    baseline_accuracy: float,
    *,
    ordinal: bool = False,
    slices: dict[str, list[bool]] | None = None,
) -> dict[str, Any]:
    """Score ``pipeline`` on the held-out set and return a JSON-ready summary."""
    y_pred = list(pipeline.predict(x_test))

    metrics: dict[str, Any] = {
        "labels": labels,
        "accuracy": round(accuracy_score(y_test, y_pred), 4),
        "macro_f1": round(f1_score(y_test, y_pred, average="macro", zero_division=0), 4),
        "weighted_f1": round(f1_score(y_test, y_pred, average="weighted", zero_division=0), 4),
        "baseline_accuracy": round(baseline_accuracy, 4),
        "per_class": per_class_metrics(y_test, y_pred, labels),
        "confusion_matrix": confusion(y_test, y_pred, labels),
        "top_features": top_features(pipeline),
        "slices": slice_metrics(y_test, y_pred, slices) if slices else [],
    }

    if ordinal:
        metrics["adjacent_accuracy"] = adjacent_accuracy(y_test, y_pred)

    return metrics


def render_report(name: str, metrics: dict[str, Any]) -> str:
    """Format one model's metrics as an aligned terminal report."""
    lines: list[str] = []
    width = 74

    lines.append("=" * width)
    lines.append(f"  {name.upper()} CLASSIFIER")
    lines.append("=" * width)

    accuracy = metrics["accuracy"]
    baseline = metrics["baseline_accuracy"]
    lift = accuracy - baseline

    lines.append(f"  Accuracy          {accuracy:.4f}")
    lines.append(f"  Macro F1          {metrics['macro_f1']:.4f}")
    lines.append(f"  Weighted F1       {metrics['weighted_f1']:.4f}")
    lines.append(f"  Majority baseline {baseline:.4f}   (lift +{lift:.4f})")

    if "adjacent_accuracy" in metrics:
        lines.append(
            f"  Within-1 accuracy {metrics['adjacent_accuracy']:.4f}   "
            "(prediction off by at most one severity level)"
        )

    lines.append("")
    lines.append(f"  {'Label':<18}{'Prec':>8}{'Recall':>8}{'F1':>8}{'Support':>9}")
    lines.append("  " + "-" * (width - 4))
    for row in metrics["per_class"]:
        lines.append(
            f"  {row['label']:<18}{row['precision']:>8.3f}"
            f"{row['recall']:>8.3f}{row['f1']:>8.3f}{row['support']:>9}"
        )

    if metrics.get("slices"):
        lines.append("")
        lines.append("  Accuracy by slice")
        for row in metrics["slices"]:
            lines.append(
                f"    {row['name']:<38} n={row['n']:<5} acc={row['accuracy']:.3f}"
            )

    lines.append("")
    lines.append("  Confusion matrix (rows = actual, columns = predicted)")
    labels = metrics["labels"]
    abbreviations = [_abbreviate(label) for label in labels]

    header = " " * 20 + "".join(f"{a:>7}" for a in abbreviations)
    lines.append(header)
    for label, row in zip(labels, metrics["confusion_matrix"], strict=True):
        lines.append(f"  {label:<18}" + "".join(f"{value:>7}" for value in row))

    lines.append("")
    lines.append("  Strongest features per class")
    for label, features in metrics["top_features"].items():
        rendered = ", ".join(f"{token}({weight:+.2f})" for token, weight in features[:5])
        lines.append(f"    {label:<18} {rendered}")

    lines.append("")
    return "\n".join(lines)


def _abbreviate(label: str) -> str:
    """Shorten a label so confusion-matrix columns stay aligned."""
    if "/" in label:
        return label.split("/")[0][:6]
    parts = label.split()
    if len(parts) > 1:
        return "".join(p[0] for p in parts).upper()
    return label[:6]
