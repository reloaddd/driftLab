
import sqlite3
import sys
from pathlib import Path

sys.path.insert(
    0,
    str(
        Path(__file__).resolve().parents[1]
        / "src"
    ),
)

from driftlab.storage import (
    log_prediction,
    store_outcome,
    recent_predictions,
    performance_report,
)


RESULT = {
    "model_version": "v1",
    "failure_probability": 0.4,
    "predicted_failure": 1,
}


def test_sources_are_isolated(tmp_path):
    db = tmp_path / "pred.sqlite3"

    a = log_prediction(
        {"Type": "L"},
        RESULT,
        db,
    )

    b = log_prediction(
        {"Type": "L"},
        RESULT,
        db,
        source="simulation",
    )

    assert store_outcome(a, 1, db)
    assert store_outcome(b, 0, db)

    evaluation_rows = recent_predictions(
        path=db,
        source="evaluation",
    )

    assert len(evaluation_rows) == 1

    assert performance_report(
        db
    )["labeled_count"] == 1

    assert performance_report(
        db,
        source="simulation",
    )["labeled_count"] == 1

    assert performance_report(
        db,
        source="production",
    )["labeled_count"] == 0


def test_old_database_is_migrated_without_trusting_records(
    tmp_path,
):
    db = tmp_path / "old.sqlite3"

    with sqlite3.connect(db) as connection:
        connection.execute("""
            CREATE TABLE predictions (
                id TEXT PRIMARY KEY,
                recorded_at TEXT NOT NULL,
                model_version TEXT NOT NULL,
                reading_json TEXT NOT NULL,
                probability REAL NOT NULL,
                prediction INTEGER NOT NULL,
                outcome INTEGER
            )
        """)

        connection.execute("""
            INSERT INTO predictions
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            "old",
            "2026-01-01",
            "v1",
            "{}",
            0.1,
            0,
            1,
        ))

    rows = recent_predictions(path=db)

    assert rows[0]["source"] == (
        "legacy_unverified"
    )

    assert performance_report(
        db
    )["labeled_count"] == 0
