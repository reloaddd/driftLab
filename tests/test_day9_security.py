
"""Day 9 registry security and safety tests."""

import json
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
sys.path.insert(0, str(PROJECT))

from api.day8 import router
from driftlab.day8_registry import switch_model


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture
def registry(tmp_path):
    """Temporary registry, never the real models folder."""

    for version in ("v1", "v2"):
        folder = tmp_path / version
        folder.mkdir()

        (folder / "metadata.json").write_text(
            json.dumps({
                "kind": "sklearn",
                "threshold": 0.3,
            }),
            encoding="utf-8",
        )

    (tmp_path / "active.json").write_text(
        json.dumps({"version": "v1"}),
        encoding="utf-8",
    )

    return tmp_path


def active(root):
    return json.loads(
        (root / "active.json").read_text(
            encoding="utf-8"
        )
    )["version"]


@pytest.mark.parametrize(
    "endpoint",
    ["/registry/promote", "/registry/rollback"],
)
def test_admin_key_required(
    monkeypatch,
    client,
    endpoint,
):
    monkeypatch.setenv(
        "DRIFTLAB_ADMIN_KEY",
        "test-secret-value",
    )

    payload = {
        "version": "v2",
        "confirmation": "ACTIVATE v2",
    }

    missing = client.post(endpoint, json=payload)

    assert missing.status_code == 403

    wrong = client.post(
        endpoint,
        json=payload,
        headers={
            "X-DriftLab-Admin-Key": "wrong-key"
        },
    )

    assert wrong.status_code == 403


def test_missing_server_configuration(
    monkeypatch,
    client,
):
    monkeypatch.delenv(
        "DRIFTLAB_ADMIN_KEY",
        raising=False,
    )

    response = client.post(
        "/registry/promote",
        json={
            "version": "v2",
            "confirmation": "ACTIVATE v2",
        },
    )

    assert response.status_code == 503


def test_unreviewed_candidate_stays_inactive(registry):
    with pytest.raises(
        ValueError,
        match="comparison",
    ):
        switch_model(
            "v2",
            confirm="ACTIVATE v2",
            root=registry,
        )

    assert active(registry) == "v1"


def test_wrong_confirmation_stays_inactive(registry):
    with pytest.raises(
        ValueError,
        match="Type ACTIVATE",
    ):
        switch_model(
            "v2",
            confirm="yes",
            root=registry,
        )

    assert active(registry) == "v1"
