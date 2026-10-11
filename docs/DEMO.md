# DriftLab — Reproducible Demo Walkthrough

**Purpose:** Demonstrate an ML service and its monitoring/governance workflow in approximately 6–10 minutes.

## Prepare

- Confirm the trusted `models/v1/` artifact and `models/active.json` exist.
- Confirm the active model is v1. Do **not** promote v2: its recorded validation metrics are worse.
- Have two AI4I sensor CSV files ready, each with at least 30 rows and the six expected features.
- Use demonstration data only. Avoid showing private tokens or actual `.env` contents.
- If necessary, back up `data/predictions.sqlite3` before replaying test predictions.

## Start

```bash
docker compose up -d
docker compose ps
```

Visit `http://127.0.0.1:8000/` and `http://127.0.0.1:8000/health`.

## Scene 1 — Why DriftLab exists (about 1 minute)

Explain that model training is only the beginning. After deployment, we need a stable input contract, consistent prediction logic, history, labelled outcomes, drift checks, and safe model versioning.

## Scene 2 — Prediction (about 2 minutes)

Use example inputs:

```json
{
  "machine_type": "L",
  "air_temperature": 302.5,
  "process_temperature": 312.8,
  "rotational_speed": 1420,
  "torque": 48.2,
  "tool_wear": 180
}
```

Point out the failure probability, the 0.30 decision threshold, model v1, and the generated prediction ID. Increase torque to 53.2 while holding other inputs fixed. In an earlier local run, the estimate increased from about 0.78% to 3.59%; rerun to show current behavior. Do not claim causal proof from a single changed input.

## Scene 3 — Prediction ledger (about 1 minute)

Open Observations. Show that predictions persist with timestamps, risk estimates, model version, and optional outcome. Explain that predictions do not become valid performance labels until ground truth is recorded.

## Scene 4 — Drift study (about 2 minutes)

Upload reference/current AI4I CSVs. Compare them first with no simulated shift. Then enable the +15 Nm torque simulation and compare again. Show changes in the torque distribution, feature scores, flags, and persistent monitoring timeline. Explain that drift is a distribution shift, not evidence of lower model accuracy.

## Scene 5 — Model governance (about 2 minutes)

Open Model Registry. Show v1 active and v2 inactive. Compare actual validation metrics:

| Metric | v1 | v2 |
| --- | ---: | ---: |
| AP | 0.7285 | 0.7249 |
| Recall | 0.7255 | 0.7059 |
| Precision | 0.7872 | 0.6316 |
| F1 | 0.7551 | 0.6667 |

Explain why v2 remains inactive. Do not trigger a real promotion in the demonstration. Mention that the management API has authentication and test-registry locking/rollback safeguards.

## Scene 6 — Engineering summary (about 1 minute)

Discuss three real problems solved: Windows policy blocked SciPy, requiring WSL; scikit-learn version mismatch broke model deserialization; and tests needed updating after adding a `source` argument. Explain why the project includes tests and dependency pinning.

## Verify and stop

```bash
python -m pytest -q tests/
docker compose logs --tail=50
docker compose down
```

Run `pytest` in the configured WSL Python environment, not inside the minimal Docker image unless test dependencies and test files are included there.

## Claims to avoid

- Do not call the estimated probability a measured machine failure rate.
- Do not claim the data is real-time industrial telemetry.
- Do not call drift proof of concept drift or declining model performance.
- Do not claim v2 was promoted or that Docker deployment alone establishes production readiness.
