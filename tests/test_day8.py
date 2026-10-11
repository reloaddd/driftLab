
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "src"),
)

from driftlab.day8_registry import (
    registry_status,
    switch_model,
)


def test_registry_status(tmp_path):
    (tmp_path / "v1").mkdir()

    (tmp_path / "v1" / "metadata.json").write_text(
        json.dumps({
            "kind": "sklearn",
            "threshold": 0.3,
        })
    )

    (tmp_path / "active.json").write_text(
        json.dumps({"version": "v1"})
    )

    status = registry_status(tmp_path)

    assert status["active_version"] == "v1"
    assert status["versions"][0]["version"] == "v1"


def test_unreviewed_challenger_is_rejected(tmp_path):
    for version in ("v1", "v2"):
        (tmp_path / version).mkdir()

        (tmp_path / version / "metadata.json").write_text(
            json.dumps({
                "kind": "sklearn",
                "threshold": 0.3,
            })
        )

    (tmp_path / "active.json").write_text(
        json.dumps({"version": "v1"})
    )

    with pytest.raises(ValueError, match="comparison"):
        switch_model(
            "v2",
            confirm="ACTIVATE v2",
            root=tmp_path,
        )

    current = json.loads(
        (tmp_path / "active.json").read_text()
    )["version"]

    assert current == "v1"


def test_requires_explicit_confirmation(tmp_path):
    (tmp_path / "active.json").write_text(
        json.dumps({"version": "v1"})
    )

    with pytest.raises(ValueError, match="Type ACTIVATE"):
        switch_model(
            "v2",
            confirm="yes",
            root=tmp_path,
        )
