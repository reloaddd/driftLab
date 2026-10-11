
"""Train and evaluate an offline challenger model."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "src"),
)

import joblib
import numpy as np
import pandas as pd
import sklearn

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    recall_score,
    precision_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from src.driftlab.schema import FEATURES
from src.driftlab.registry import (
    active_version,
    model_dir,
    registry_root,
)
from src.driftlab.prediction import load_model


TARGET = "Machine failure"


def read_data(path):
    df = pd.read_csv(path)

    required = FEATURES + [TARGET]
    missing = set(required) - set(df.columns)

    if missing:
        raise ValueError(
            f"Missing columns: {sorted(missing)}"
        )

    if df[required].isna().any().any():
        raise ValueError("Null inputs are not supported")

    if not set(df[TARGET].unique()).issubset({0, 1}):
        raise ValueError("Target must be binary")

    if not set(df["Type"].unique()).issubset({"L", "M", "H"}):
        raise ValueError("Invalid machine type")

    X = df[FEATURES].copy()

    for column in FEATURES[1:]:
        X[column] = pd.to_numeric(
            X[column],
            errors="raise",
        )

    if not np.isfinite(
        X[FEATURES[1:]].to_numpy(dtype=float)
    ).all():
        raise ValueError("Non-finite features")

    y = df[TARGET].astype(int).to_numpy()

    return X, y


def evaluate(model, X, y, threshold):
    probability = np.asarray(
        model.predict_proba(X)[:, 1],
        dtype=float,
    )

    prediction = (
        probability >= threshold
    ).astype(int)

    return {
        "average_precision": float(
            average_precision_score(y, probability)
        ),
        "recall": float(
            recall_score(y, prediction, zero_division=0)
        ),
        "precision": float(
            precision_score(y, prediction, zero_division=0)
        ),
        "f1": float(
            f1_score(y, prediction, zero_division=0)
        ),
        "threshold": float(threshold),
    }


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--train", required=True)
    parser.add_argument("--validation", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.30,
    )

    args = parser.parse_args()

    if not 0 < args.threshold < 1:
        parser.error(
            "Threshold must be between 0 and 1"
        )

    root = registry_root()
    champion = active_version(root)
    destination = model_dir(args.version, root)

    if destination.exists():
        parser.error(
            "Candidate version already exists"
        )

    if args.version == champion:
        parser.error(
            "Candidate must use a new version"
        )

    X_train, y_train = read_data(args.train)
    X_val, y_val = read_data(args.validation)

    if (
        len(np.unique(y_train)) != 2
        or len(np.unique(y_val)) != 2
    ):
        parser.error(
            "Both datasets must contain both classes"
        )

    # Check for duplicate sensor rows across partitions.
    train_rows = set(
        map(
            tuple,
            X_train.itertuples(
                index=False,
                name=None,
            ),
        )
    )

    if any(
        tuple(row) in train_rows
        for row in X_val.itertuples(
            index=False,
            name=None,
        )
    ):
        parser.error(
            "Training/validation overlap detected"
        )

    current_model, _, current_metadata = load_model(
        champion,
        str(root.resolve()),
    )

    if current_metadata.get("kind") != "sklearn":
        parser.error(
            "This command supports sklearn champions only"
        )

    numeric = FEATURES[1:]

    transformer = ColumnTransformer([
        (
            "numeric",
            "passthrough",
            numeric,
        ),
        (
            "category",
            OneHotEncoder(
                handle_unknown="ignore"
            ),
            ["Type"],
        ),
    ])

    challenger = Pipeline([
        ("preprocessor", transformer),
        (
            "classifier",
            RandomForestClassifier(
                n_estimators=300,
                min_samples_leaf=2,
                class_weight="balanced_subsample",
                random_state=42,
                n_jobs=-1,
            ),
        ),
    ])

    challenger.fit(X_train, y_train)

    champion_threshold = float(
        current_metadata["threshold"]
    )

    champion_metrics = evaluate(
        current_model,
        X_val,
        y_val,
        champion_threshold,
    )

    challenger_metrics = evaluate(
        challenger,
        X_val,
        y_val,
        args.threshold,
    )

    # A heuristic screening rule, not final approval.
    improved = (
        challenger_metrics["average_precision"]
        > champion_metrics["average_precision"]
        and challenger_metrics["recall"]
        >= champion_metrics["recall"]
    )

    report = {
        "champion_version": champion,
        "candidate_version": args.version,
        "champion": champion_metrics,
        "challenger": challenger_metrics,
        "approved_for_review": bool(improved),
        "validation_count": len(y_val),
        "notice": (
            "Review the validation cohort and errors. "
            "Never use final test data for model selection."
        ),
    }

    destination.mkdir(
        parents=True,
        exist_ok=False,
    )

    try:
        joblib.dump(
            challenger,
            destination / "model.joblib",
        )

        metadata = {
            "kind": "sklearn",
            "threshold": args.threshold,
            "trained_with": "Day8 offline RandomForest",
            "sklearn_version": sklearn.__version__,
        }

        (destination / "metadata.json").write_text(
            json.dumps(metadata, indent=2),
            encoding="utf-8",
        )

        (destination / "evaluation.json").write_text(
            json.dumps(report, indent=2),
            encoding="utf-8",
        )

    except BaseException:
        import shutil
        shutil.rmtree(destination)
        raise

    print(json.dumps(report, indent=2))

    print(
        f"Candidate saved at {destination}. "
        f"Active model remains {champion}."
    )


if __name__ == "__main__":
    main()
