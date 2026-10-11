from pathlib import Path
import json
from functools import lru_cache
import joblib
import numpy as np
import pandas as pd
import torch
from torch import nn
from .registry import active_version, model_dir
from .schema import FEATURES, SensorReading

class FailureMLP(nn.Module):
    def __init__(self, n_features: int):
        super().__init__()
        self.network = nn.Sequential(nn.Linear(n_features, 32), nn.ReLU(), nn.Linear(32, 16), nn.ReLU(), nn.Linear(16, 1))
    def forward(self, x):
        return self.network(x).squeeze(1)

@lru_cache(maxsize=8)
def load_model(version: str, root_str: str):
    directory = model_dir(version, Path(root_str))
    metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    kind = metadata["kind"]
    if kind == "sklearn":
        # joblib uses pickle internally; never load untrusted files.
        model = joblib.load(directory / "model.joblib")
        return model, None, metadata
    if kind == "torch":
        preprocessor = joblib.load(directory / "preprocessor.joblib")
        network = FailureMLP(int(metadata["input_features"]))
        network.load_state_dict(torch.load(directory / "model.pt", map_location="cpu", weights_only=True))
        network.eval()
        return network, preprocessor, metadata
    raise ValueError(f"Unsupported model kind {kind}")


def predict(reading: SensorReading, root: Path | None = None, version: str | None = None):
    from .registry import registry_root
    root = root or registry_root()
    version = version or active_version(root)
    model, preprocessor, metadata = load_model(version, str(root.resolve()))
    frame = pd.DataFrame([reading.to_features()], columns=FEATURES)
    if metadata["kind"] == "sklearn":
        probability = float(model.predict_proba(frame)[0, 1])
    else:
        features = np.asarray(preprocessor.transform(frame), dtype=np.float32)
        with torch.inference_mode():
            probability = float(torch.sigmoid(model(torch.from_numpy(features)))[0])
    threshold = float(metadata["threshold"])
    label = int(probability >= threshold)
    return {"failure_probability": probability, "predicted_failure": label,
            "threshold": threshold, "model_version": version, "risk_level": "HIGH" if label else "LOW"}
