
"""Verify deployed inference agrees with the saved model."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

PROJECT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / "src"))

from driftlab.registry import registry_root
from driftlab.prediction import load_model
from driftlab.schema import SensorReading
from api.main import predict_endpoint


def test_saved_model_matches_api(monkeypatch, tmp_path):
    # Isolate prediction logging from the normal DB.
    import driftlab.storage as storage
    import api.main as api_main

    def temporary_log(features, result,source="evaluation"):
        return storage.log_prediction(
            features,
            result,
            tmp_path / "inference_test.sqlite3",
            source=source
        )

    monkeypatch.setattr(
        api_main,
        "log_prediction",
        temporary_log,
    )

    reading = SensorReading(
        machine_type="L",
        air_temperature=302.5,
        process_temperature=312.8,
        rotational_speed=1420,
        torque=53.2,
        tool_wear=180,
    )

    from driftlab.registry import active_version

    version = active_version()
    model, _, metadata = load_model(
        version,
        str(registry_root().resolve()),
    )

    if metadata.get("kind") != "sklearn":
        pytest.skip("Direct sklearn comparison only")

    frame = pd.DataFrame(
        [reading.to_features()]
    )

    direct_probability = float(
        np.asarray(model.predict_proba(frame))[0, 1]
    )

    response = predict_endpoint(reading)

    assert response["model_version"] == version

    assert response["failure_probability"] == pytest.approx(
        direct_probability,
        abs=1e-8,
    )

    expected_class = int(
        direct_probability >= float(metadata["threshold"])
    )

    assert response["predicted_failure"] == expected_class

    assert response["prediction_id"]
