# DriftLab

**A predictive-maintenance ML system with inference, monitoring, drift analysis, and controlled model governance.**

DriftLab is an end-to-end machine-learning engineering project built using the UCI AI4I 2020 predictive-maintenance dataset. It starts with exploratory analysis and model training, then turns the trained model into a local web application that records predictions, evaluates known outcomes, compares sensor distributions, and manages candidate model versions.

> **Project status:** Local Docker deployment reported working. This is a demonstration/portfolio system, not a certified industrial failure-prediction product.

## Why this project?

A notebook can tell us whether a model predicts well on held-out data. It doesn't show how a model behaves as a service, how predictions are recorded, how new data might change, or when a replacement model should be rejected. DriftLab explores those additional responsibilities.

## Features

- AI4I 2020 EDA, leakage-aware feature selection, stratified splitting, and model comparison in a master Colab notebook.
- Versioned model artifacts and FastAPI endpoints for inference and model information.
- An editorial-style HTML/CSS/vanilla JavaScript interface for machine assessments and monitoring.
- SQLite prediction history, recorded outcomes, and performance reporting.
- CSV-based reference/current sensor drift comparisons using PSI for numeric measurements and total variation for machine type.
- Stored drift-check history, including a declared simulation marker.
- Offline challenger training, validation comparisons, explicit review, and protected model-management operations.
- Docker Compose configuration for local application startup.

## Architecture

```text
                 AI4I 2020 dataset
                        |
                        v
            DriftLab.ipynb (Colab)
       EDA -> split -> preprocessing -> train
                        |
                        v
           Versioned model artifacts
                models/active.json
                        |
                        v
Browser UI <-----> FastAPI application
                        |
           +------------+------------+
           |            |            |
      Inference     Monitoring     Registry
           |            |            |
           +-------> SQLite     Model versions
                   prediction &  manual approval
                   drift history
```

The notebook is for experimentation/training. The API loads a saved model for serving; users do not need to run the notebook to generate predictions.

For more details see [Architecture](docs/ARCHITECTURE.md).

## Tech stack

| Layer | Technology |
| --- | --- |
| Dataset | UCI AI4I 2020 |
| ML experiments | pandas, NumPy, scikit-learn, PyTorch, Google Colab |
| API | Python, FastAPI, Uvicorn |
| Persistence | SQLite |
| UI | HTML, CSS, vanilla JavaScript, SVG |
| Tests | pytest |
| Packaging | Docker, Docker Compose |

## Features and leakage prevention

The model uses six inputs: `Type`, `Air temperature [K]`, `Process temperature [K]`, `Rotational speed [rpm]`, `Torque [Nm]`, and `Tool wear [min]`.

Identifiers (`UDI`, `Product ID`) and failure-mode labels (`TWF`, `HDF`, `PWF`, `OSF`, `RNF`) are excluded from model inputs to avoid identifier misuse and target leakage.

The dataset has 10,000 observations and 339 machine-failure labels. Because failures are uncommon, evaluation considers precision, recall, F1, and average precision instead of relying on accuracy alone.

## Champion versus challenger: actual validation comparison

Both models were evaluated on the same 1,500-row validation partition, using a decision threshold of 0.30.

| Metric | v1 champion | v2 challenger |
| --- | ---: | ---: |
| Average precision | 0.7285 | 0.7249 |
| Recall | 0.7255 | 0.7059 |
| Precision | 0.7872 | 0.6316 |
| F1 | 0.7551 | 0.6667 |

The v2 challenger did not meet the review criteria. **v1 remains the active model.** These are validation results, not measured production performance.

## Run locally with Docker

Prerequisites: Docker Engine/Desktop with Compose access, existing trusted model artifacts in `models/`, and a reviewed `deployment/requirements-lock.txt`.

```bash
docker compose build
docker compose up -d
docker compose ps
```

Open:

- Dashboard: `http://127.0.0.1:8000/`
- API documentation: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/health`
- Registry: `http://127.0.0.1:8000/registry/status`

Stop with `docker compose down`. Local `models/` and `data/` directories are bind-mounted; do not commit sensitive `.env` values, SQLite data, or untrusted model binaries.

Alternatively, run with the verified Linux virtual environment:

```bash
source .venv-linux/bin/activate
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Saved scikit-learn objects can fail to load across library versions. The v1 artifact was created with scikit-learn 1.6.1; match the training environment when serving it. Load only trusted serialized artifacts.

## Main API endpoints

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Check model readiness |
| `GET /model/info` | Model metadata |
| `POST /predict` | Failure probability, class, risk, prediction ID |
| `GET /monitor/recent` | Recent stored predictions |
| `POST /outcomes/{prediction_id}` | Attach a known outcome |
| `GET /monitor/performance` | Labelled prediction metrics, filterable by source/version |
| `POST /monitor/drift` | Compare sensor batches |
| `GET /monitor/drift/history` | Stored drift comparisons |
| `GET /registry/status` | Active version and candidate reports |
| `POST /registry/promote` | Administrator-protected reviewed promotion |
| `POST /registry/rollback` | Administrator-protected rollback |

## Tests

The local WSL regression suite reached **21 tests after the Day 9 monitoring-source correction**, as reported during development. Test coverage includes security, prediction consistency, SQLite records, drift history, and isolated registry lifecycle behavior. Re-run tests in your environment before publishing an exact current test count:

```bash
python -m pytest -q tests/
```

## What this project taught me

1. Reliable ML starts with data definition, leakage prevention, and evaluation aligned with the real problem.
2. Serving requires the same fitted preprocessing, model, threshold, and compatible dependency versions.
3. Predictions are not outcomes; performance monitoring depends on labels collected later.
4. Input drift alone does not prove degraded accuracy.
5. Retraining is not automatically an improvement: a candidate must be evaluated and can be rejected.
6. Production-style engineering includes persistence, versioning, security checks, tests, and reproducibility.

## Limitations and future improvements

- AI4I is a public teaching dataset; this application is not validated on live industrial machines.
- Uploaded drift datasets and outcome labels are not independently authenticated as operational truth.
- Some older database records are categorized as `legacy_unverified`; UI submissions are evaluation data.
- Drift statistics are screening heuristics and can be unstable for small or highly discrete samples.
- A model activation pointer change and the audit-log write are not fully transactional across crashes.
- The local token-protected registry is not a complete production identity/authorization system.
- No distributed monitoring scheduler, alert dispatch, or live sensor ingestion has been verified.

See [Demo guide](docs/DEMO.md) to reproduce a complete walkthrough.
