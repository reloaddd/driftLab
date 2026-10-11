
"""SQLite prediction journal with explicit data provenance."""

from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
import uuid

DEFAULT_DB = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "predictions.sqlite3"
)

SOURCES = {
    "evaluation",
    "simulation",
    "production",
    "legacy_unverified",
}


def _connect(path=None):
    target = (
        Path(path)
        if path is not None
        else DEFAULT_DB
    )

    target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    db = sqlite3.connect(
        target,
        timeout=15,
    )

    db.row_factory = sqlite3.Row

    db.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id TEXT PRIMARY KEY,
            recorded_at TEXT NOT NULL,
            model_version TEXT NOT NULL,
            reading_json TEXT NOT NULL,
            probability REAL NOT NULL,
            prediction INTEGER NOT NULL,
            outcome INTEGER CHECK (
                outcome IN (0,1)
                OR outcome IS NULL
            ),
            source TEXT NOT NULL
                DEFAULT 'legacy_unverified'
        )
    """)

    # Migrate an existing Day 5–8 database safely.
    columns = {
        row["name"]
        for row in db.execute(
            "PRAGMA table_info(predictions)"
        )
    }

    if "source" not in columns:
        db.execute("""
            ALTER TABLE predictions
            ADD COLUMN source TEXT NOT NULL
            DEFAULT 'legacy_unverified'
        """)

        db.commit()

    return db


def log_prediction(
    reading,
    result,
    path=None,
    *,
    source="evaluation",
):
    if source not in SOURCES:
        raise ValueError(
            "Invalid prediction source"
        )

    identifier = str(uuid.uuid4())

    with _connect(path) as db:
        db.execute("""
            INSERT INTO predictions (
                id,
                recorded_at,
                model_version,
                reading_json,
                probability,
                prediction,
                outcome,
                source
            )
            VALUES (?, ?, ?, ?, ?, ?, NULL, ?)
        """, (
            identifier,
            datetime.now(
                timezone.utc
            ).isoformat(),
            result["model_version"],
            json.dumps(
                reading,
                allow_nan=False,
            ),
            result["failure_probability"],
            result["predicted_failure"],
            source,
        ))

    return identifier


def store_outcome(
    identifier,
    outcome,
    path=None,
):
    if outcome not in (0, 1):
        raise ValueError(
            "Outcome must be 0 or 1"
        )

    with _connect(path) as db:
        result = db.execute("""
            UPDATE predictions
            SET outcome=?
            WHERE id=?
              AND outcome IS NULL
        """, (
            outcome,
            identifier,
        ))

        return result.rowcount == 1


def recent_predictions(
    limit=500,
    path=None,
    *,
    source=None,
):
    if not 1 <= limit <= 100000:
        raise ValueError(
            "limit must be 1..100000"
        )

    if (
        source is not None
        and source not in SOURCES
    ):
        raise ValueError(
            "Invalid prediction source"
        )

    query = "SELECT * FROM predictions"
    params = []

    if source is not None:
        query += " WHERE source=?"
        params.append(source)

    query += (
        " ORDER BY recorded_at DESC, id DESC"
        " LIMIT ?"
    )

    params.append(limit)

    with _connect(path) as db:
        rows = db.execute(
            query,
            params,
        ).fetchall()

    return [
        {
            **dict(row),
            "reading": json.loads(
                row["reading_json"]
            ),
        }
        for row in rows
    ]


def performance_report(
    path=None,
    min_labeled=20,
    *,
    source="evaluation",
    model_version=None,
):
    if source not in SOURCES:
        raise ValueError(
            "Invalid prediction source"
        )

    if min_labeled < 1:
        raise ValueError(
            "min_labeled must be positive"
        )

    query = """
        SELECT outcome, prediction, probability
        FROM predictions
        WHERE outcome IS NOT NULL
          AND source=?
    """

    params = [source]

    if model_version is not None:
        query += " AND model_version=?"
        params.append(model_version)

    with _connect(path) as db:
        rows = db.execute(
            query,
            params,
        ).fetchall()

    result = {
        "labeled_count": len(rows),
        "source": source,
        "model_version": model_version,
    }

    if len(rows) < min_labeled:
        return {
            **result,
            "status": "insufficient_labels",
            "required": min_labeled,
        }

    # Load sklearn only when metrics are needed.
    from sklearn.metrics import (
        precision_score,
        recall_score,
        f1_score,
        average_precision_score,
    )

    y = [
        row["outcome"]
        for row in rows
    ]

    pred = [
        row["prediction"]
        for row in rows
    ]

    prob = [
        row["probability"]
        for row in rows
    ]

    return {
        **result,
        "status": "ok",
        "precision": float(
            precision_score(
                y,
                pred,
                zero_division=0,
            )
        ),
        "recall": float(
            recall_score(
                y,
                pred,
                zero_division=0,
            )
        ),
        "f1": float(
            f1_score(
                y,
                pred,
                zero_division=0,
            )
        ),
        "average_precision": (
            float(
                average_precision_score(
                    y,
                    prob,
                )
            )
            if len(set(y)) == 2
            else None
        ),
        "caution": (
            "Source is declared, not independently "
            "verified. Filter by model version "
            "before making deployment decisions."
        ),
    }
