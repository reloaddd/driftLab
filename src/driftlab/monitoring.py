"""Numerical PSI and categorical total variation drift checks."""
import numpy as np
import pandas as pd
from .schema import FEATURES

NUMERIC = FEATURES[1:]

def _psi(reference, current, bins=10):
    reference = np.asarray(reference, dtype=float)
    current = np.asarray(current, dtype=float)
    if not np.isfinite(reference).all() or not np.isfinite(current).all():
        raise ValueError("Drift inputs must contain finite measurements")
    edges = np.unique(np.quantile(reference, np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:
        return 0.0 if np.array_equal(np.unique(reference), np.unique(current)) else None
    edges[0] = -np.inf
    edges[-1] = np.inf
    ref_counts = np.histogram(reference, bins=edges)[0]
    now_counts = np.histogram(current, bins=edges)[0]
    # Laplace-style smoothing prevents log(0); PSI is sample-size sensitive.
    p = (ref_counts + 0.5) / (len(reference) + 0.5 * len(ref_counts))
    q = (now_counts + 0.5) / (len(current) + 0.5 * len(now_counts))
    return float(np.sum((q - p) * np.log(q / p)))

def drift_report(reference: pd.DataFrame, current: pd.DataFrame, min_rows=30, psi_threshold=0.2):
    """Compare unlabeled batches. Flags are heuristics, not proof of model degradation."""
    for frame in (reference, current):
        if not set(FEATURES).issubset(frame.columns):
            raise ValueError("Both datasets require the six model features")
        if len(frame) < min_rows:
            raise ValueError(f"At least {min_rows} observations required in each batch")
    report = {}
    for feature in NUMERIC:
        value = _psi(reference[feature], current[feature])
        report[feature] = {"metric":"psi", "value":value, "drift": None if value is None else value >= psi_threshold}
    categories = ['L','M','H']
    p = reference['Type'].value_counts(normalize=True).reindex(categories, fill_value=0)
    q = current['Type'].value_counts(normalize=True).reindex(categories, fill_value=0)
    tvd = float(0.5 * np.abs(p-q).sum())
    report['Type'] = {"metric":"total_variation", "value":tvd, "drift":tvd >= 0.15}
    return {"reference_size":len(reference), "current_size":len(current),
            "features":report, "flagged_features":[k for k,v in report.items() if v['drift'] is True],
            "notice":"Drift flags alone do not imply reduced predictive accuracy."}
