"""Train, evaluate and persist the TriageAI classifiers.

Usage::

    python -m ml.train                  # train both, write artifacts + metrics
    python -m ml.train --no-search      # skip the grid search (fast iteration)

What this script produces, in ``app/ml/artifacts/``:

    category_model.joblib   fitted Pipeline(tfidf -> logistic regression)
    urgency_model.joblib    fitted Pipeline(tfidf -> logistic regression)
    metrics.json            everything the dashboard's model panel renders

Three decisions are made here that are worth being able to justify out loud.

**Why a Pipeline rather than a separate vectoriser file.** The vectoriser and
the classifier are saved as one object. Persisting them separately invites the
classic failure where a model is loaded next to a vectoriser fitted on a
different vocabulary — the shapes still line up, the predictions are quietly
garbage. One artifact makes that unrepresentable.

**Why the preprocessor is passed by reference.** ``TfidfVectorizer`` receives
``app.ml.preprocess.preprocess`` itself, so joblib stores a *reference* to that
function rather than a copy. The serving path physically cannot use different
cleaning logic from the training path.

**Why logistic regression and not the linear SVM.** Both are evaluated below
and the SVM is usually a hair better on macro F1. Logistic regression still
wins, because the product requires a calibrated ``predict_proba`` for the
per-class confidence bars in the UI. ``LinearSVC`` exposes only unbounded
decision-function margins; turning those into probabilities needs a
``CalibratedClassifierCV`` wrapper, which costs an inner cross-validation loop
and destroys the direct coefficient interpretability that makes the "why did
the model say this" panel possible. A fraction of a point of F1 is not worth
that trade.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import sklearn
from joblib import dump
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GridSearchCV, StratifiedKFold, cross_validate, train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ml.preprocess import preprocess  # noqa: E402
from app.ml.taxonomy import CATEGORIES, URGENCIES  # noqa: E402
from ml.evaluate import evaluate_model, render_report  # noqa: E402

BACKEND_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = BACKEND_ROOT / "data" / "tickets.csv"
ARTIFACT_DIR = BACKEND_ROOT / "app" / "ml" / "artifacts"

RANDOM_STATE = 42
TEST_SIZE = 0.2
CV_FOLDS = 5

# Searched jointly for each target. Kept deliberately small: with ~1100
# training rows a wider grid mostly fits noise in the cross-validation folds,
# and the honest story is "I searched the parameters that matter" rather than
# "I searched everything and took the max".
PARAM_GRID: dict[str, list[Any]] = {
    # Bigrams are the reason this is worth searching at all. Urgency lives in
    # phrases — "not urgent", "no rush", "production down" — where the
    # individual unigrams are ambiguous or actively misleading.
    "tfidf__ngram_range": [(1, 1), (1, 2)],
    "tfidf__min_df": [1, 2],
    "clf__C": [0.5, 1.0, 2.0, 4.0],
}


def build_pipeline(**classifier_kwargs: Any) -> Pipeline:
    """Assemble the cleaning -> vectorising -> classifying pipeline."""
    return Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    preprocessor=preprocess,
                    ngram_range=(1, 2),
                    min_df=2,
                    max_df=0.9,
                    # Dampens the effect of a word repeated many times in one
                    # ticket. An angry customer writing "broken" six times is
                    # not six times more informative than writing it once.
                    sublinear_tf=True,
                    strip_accents=None,  # already handled in preprocess()
                    lowercase=False,  # already handled in preprocess()
                ),
            ),
            (
                "clf",
                LogisticRegression(
                    max_iter=2000,
                    # The label priors are intentionally skewed (Critical is
                    # ~14% of the corpus). Without this the model learns to
                    # under-predict the rare-but-expensive classes, which is
                    # exactly backwards for a triage tool: missing a Critical
                    # ticket costs far more than over-flagging a Low one.
                    class_weight="balanced",
                    random_state=RANDOM_STATE,
                    **classifier_kwargs,
                ),
            ),
        ]
    )


def compare_candidates(x_train: list[str], y_train: list[str]) -> list[dict[str, Any]]:
    """Cross-validate several classifier families on the training split.

    Run so the choice of logistic regression is defended with numbers rather
    than assertion. Scored on the training split only — the held-out set is
    never touched during model selection.
    """
    candidates: dict[str, Any] = {
        "Majority baseline": DummyClassifier(strategy="most_frequent"),
        "Multinomial NB": MultinomialNB(),
        "Linear SVM": LinearSVC(class_weight="balanced", random_state=RANDOM_STATE),
        "Logistic Regression": LogisticRegression(
            max_iter=2000, class_weight="balanced", random_state=RANDOM_STATE
        ),
    }

    folds = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)
    results: list[dict[str, Any]] = []

    for name, classifier in candidates.items():
        pipeline = Pipeline(
            [
                (
                    "tfidf",
                    TfidfVectorizer(
                        preprocessor=preprocess,
                        ngram_range=(1, 2),
                        min_df=2,
                        max_df=0.9,
                        sublinear_tf=True,
                        lowercase=False,
                    ),
                ),
                ("clf", classifier),
            ]
        )
        scores = cross_validate(
            pipeline,
            x_train,
            y_train,
            cv=folds,
            scoring=["accuracy", "f1_macro"],
            n_jobs=-1,
        )
        results.append(
            {
                "model": name,
                "cv_accuracy": round(float(scores["test_accuracy"].mean()), 4),
                "cv_accuracy_std": round(float(scores["test_accuracy"].std()), 4),
                "cv_macro_f1": round(float(scores["test_f1_macro"].mean()), 4),
                "fit_seconds": round(float(scores["fit_time"].mean()), 3),
            }
        )

    return results


def train_target(
    name: str,
    x_train: list[str],
    y_train: list[str],
    *,
    run_search: bool,
) -> tuple[Pipeline, dict[str, Any]]:
    """Fit one target, optionally grid-searching first. Returns model + search info."""
    print(f"\n[{name}] cross-validating candidate model families...")
    comparison = compare_candidates(x_train, y_train)
    for row in comparison:
        print(
            f"    {row['model']:<22} acc={row['cv_accuracy']:.4f} "
            f"(+/-{row['cv_accuracy_std']:.4f})  macroF1={row['cv_macro_f1']:.4f}"
        )

    if not run_search:
        print(f"[{name}] skipping grid search, fitting with defaults...")
        pipeline = build_pipeline()
        pipeline.fit(x_train, y_train)
        return pipeline, {"candidates": comparison, "best_params": None, "cv_best_score": None}

    print(f"[{name}] grid-searching hyperparameters...")
    folds = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)
    search = GridSearchCV(
        build_pipeline(),
        PARAM_GRID,
        # Macro F1, not accuracy. Accuracy is dominated by the majority class,
        # and a triage model that quietly gives up on Critical tickets while
        # nailing Medium ones would still look fine on accuracy.
        scoring="f1_macro",
        cv=folds,
        n_jobs=-1,
        refit=True,
    )
    search.fit(x_train, y_train)

    print(f"[{name}] best macro F1 (cv) = {search.best_score_:.4f}")
    print(f"[{name}] best params        = {search.best_params_}")

    return search.best_estimator_, {
        "candidates": comparison,
        "best_params": {k: str(v) for k, v in search.best_params_.items()},
        "cv_best_score": round(float(search.best_score_), 4),
    }


def stratify_key(frame: pd.DataFrame) -> pd.Series | None:
    """Build the stratification key for the shared train/test split.

    Stratifying on the joint (category, urgency) label keeps both marginal
    distributions intact in the held-out set. Some joint cells are genuinely
    tiny by design — Feature Request x Critical is ~0.1% of the corpus — and
    scikit-learn refuses to stratify a class with fewer than two members, so
    fall back to category alone if any cell is too small to split.
    """
    joint = frame["category"] + " | " + frame["urgency"]
    if joint.value_counts().min() >= 2:
        return joint

    print("  note: joint stratification not possible (a cell has <2 rows); "
          "stratifying on category only")
    return frame["category"]


def build_slices(test_frame: pd.DataFrame, target: str) -> dict[str, list[bool]]:
    """Named subsets of the test split to report accuracy on separately.

    The generator records two provenance flags per ticket — whether the
    reporter stated their impact, and whether the label was moved by simulated
    annotator disagreement. Neither is ever shown to the model; they exist
    purely so the evaluation can explain *where* the errors live.
    """
    slices: dict[str, list[bool]] = {}

    if "label_noise" in test_frame:
        slices["Labels free of annotator noise"] = (~test_frame["label_noise"]).tolist()

    # Only meaningful for urgency — the "did they say how bad it is" flag has
    # no bearing on which category a ticket belongs to.
    if target == "urgency" and "urgency_stated" in test_frame:
        slices["Reporter stated the impact"] = test_frame["urgency_stated"].tolist()
        slices["Impact left implicit"] = (~test_frame["urgency_stated"]).tolist()

    return slices


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the TriageAI classifiers.")
    parser.add_argument("--data", type=Path, default=DATA_PATH)
    parser.add_argument("--out", type=Path, default=ARTIFACT_DIR)
    parser.add_argument(
        "--no-search", action="store_true", help="skip grid search and use defaults"
    )
    args = parser.parse_args()

    if not args.data.exists():
        raise SystemExit(
            f"Dataset not found at {args.data}. Run: python -m ml.generate_dataset"
        )

    frame = pd.read_csv(args.data)
    print(f"Loaded {len(frame)} tickets from {args.data}")

    # One split shared by both targets, so "the test set" means the same set of
    # tickets in both reports and the two models are directly comparable.
    train_frame, test_frame = train_test_split(
        frame,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        stratify=stratify_key(frame),
    )
    x_train = train_frame["ticket_text"].tolist()
    x_test = test_frame["ticket_text"].tolist()
    print(f"Split: {len(x_train)} train / {len(x_test)} test")

    metrics: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "dataset": {
            "total": int(len(frame)),
            "train": int(len(x_train)),
            "test": int(len(x_test)),
            "source": str(args.data.name),
        },
        "environment": {
            "python": platform.python_version(),
            "scikit_learn": sklearn.__version__,
        },
        "models": {},
    }

    args.out.mkdir(parents=True, exist_ok=True)
    reports: list[str] = []

    targets = [
        ("category", CATEGORIES, False),
        ("urgency", URGENCIES, True),
    ]

    for target, labels, ordinal in targets:
        y_train = train_frame[target].tolist()
        y_test = test_frame[target].tolist()

        model, search_info = train_target(
            target, x_train, y_train, run_search=not args.no_search
        )

        # The majority-class rate on the *test* split. Quoting accuracy without
        # this is meaningless — 60% sounds good until the baseline is 58%.
        baseline = max(y_test.count(label) for label in labels) / len(y_test)

        target_metrics = evaluate_model(
            model,
            x_test,
            y_test,
            labels,
            baseline,
            ordinal=ordinal,
            slices=build_slices(test_frame, target),
        )
        target_metrics["model_selection"] = search_info
        metrics["models"][target] = target_metrics

        artifact_path = args.out / f"{target}_model.joblib"
        dump(model, artifact_path, compress=3)
        print(f"[{target}] saved -> {artifact_path.relative_to(BACKEND_ROOT)}")

        reports.append(render_report(target, target_metrics))

    metrics_path = args.out / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    print("\n" + "\n".join(reports))
    print(f"Metrics written to {metrics_path.relative_to(BACKEND_ROOT)}")


if __name__ == "__main__":
    main()
