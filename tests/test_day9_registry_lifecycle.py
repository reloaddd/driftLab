
"""Isolated registry lifecycle tests. Never touch the real models."""

import json
import sys

from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import pytest

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "src"),
)

from driftlab import day8_registry as registry


def setup_registry(root):
    for version in ("v1", "v2"):
        folder = root / version
        folder.mkdir()

        (folder / "metadata.json").write_text(
            json.dumps({
                "kind": "sklearn",
                "threshold": 0.3,
            })
        )

    (root / "active.json").write_text(
        json.dumps({"version": "v1"})
    )

    (root / "v2" / "evaluation.json").write_text(
        json.dumps({
            "champion_version": "v1",
            "candidate_version": "v2",
            "approved_for_review": True,
        })
    )


def test_promotion_and_rollback(monkeypatch, tmp_path):
    setup_registry(tmp_path)

    monkeypatch.setattr(
        registry,
        "load_model",
        Mock(return_value=("test-model", None, {})),
    )

    result = registry.switch_model(
        "v2",
        confirm="ACTIVATE v2",
        root=tmp_path,
    )

    assert result["active_version"] == "v2"
    assert registry.active_version(tmp_path) == "v2"

    result = registry.switch_model(
        "v1",
        confirm="ACTIVATE v1",
        root=tmp_path,
        allow_rollback=True,
    )

    assert result["active_version"] == "v1"
    assert registry.active_version(tmp_path) == "v1"
    assert len(registry._events(tmp_path)) == 2


def test_rollback_without_prior_activation_rejected(tmp_path):
    setup_registry(tmp_path)

    with pytest.raises(
        ValueError,
        match="immediate previous",
    ):
        registry.switch_model(
            "v2",
            confirm="ACTIVATE v2",
            root=tmp_path,
            allow_rollback=True,
        )

    assert registry.active_version(tmp_path) == "v1"


def test_racing_promotions_do_not_both_succeed(
    monkeypatch,
    tmp_path,
):
    setup_registry(tmp_path)

    monkeypatch.setattr(
        registry,
        "load_model",
        Mock(return_value=("test-model", None, {})),
    )

    def attempt(_):
        try:
            registry.switch_model(
                "v2",
                confirm="ACTIVATE v2",
                root=tmp_path,
            )
            return "ok"

        except ValueError:
            return "rejected"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(
            attempt,
            range(2),
        ))

    assert sorted(results) == [
        "ok",
        "rejected",
    ]

    assert registry.active_version(tmp_path) == "v2"
    assert len(registry._events(tmp_path)) == 1
