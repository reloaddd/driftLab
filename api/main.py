from pathlib import Path
import sys
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from driftlab.storage import log_prediction, store_outcome, recent_predictions, performance_report
from driftlab.monitoring import drift_report
import pandas as pd

from driftlab.schema import SensorReading
from driftlab.registry import active_version, registry_root
from driftlab.prediction import predict, load_model


app = FastAPI(title='DriftLab — ML Monitoring API', version='0.5.0')

from api.day8 import router as registry_router

app.include_router(registry_router)

@app.get('/health')
def health():
    try:
        version = active_version()
        load_model(version, str(registry_root().resolve()))
        return {'status': 'ready', 'model_version': version}
    except (FileNotFoundError, KeyError, ValueError, OSError):
        return {'status': 'model_unavailable', 'model_version': None}

@app.get('/model/info')
def model_info():
    try:
        version = active_version()
        _, _, metadata = load_model(version, str(registry_root().resolve()))
        return {'version': version, **metadata}
    except (FileNotFoundError, KeyError, ValueError, OSError) as exc:
        raise HTTPException(status_code=503, detail='Model not loaded') from exc

@app.post('/predict')
def predict_endpoint(reading: SensorReading):
    try:
        result = predict(reading)
        result["prediction_id"] = log_prediction(reading.to_features(), result, source="evaluation")
        return result
    except (FileNotFoundError, KeyError, ValueError, OSError) as exc:
        raise HTTPException(status_code=503, detail='Model unavailable') from exc

class OutcomePayload(BaseModel):
    outcome: int = Field(ge=0, le=1)

class DriftPayload(BaseModel):
    reference: list[SensorReading] = Field(min_length=30)
    current: list[SensorReading] = Field(min_length=30)

@app.post('/outcomes/{prediction_id}')
def record_outcome(prediction_id: str, payload: OutcomePayload):
    if not store_outcome(prediction_id, payload.outcome):
        raise HTTPException(status_code=404, detail='Prediction missing or outcome already recorded')
    return {'prediction_id':prediction_id, 'outcome_recorded':True}

@app.get("/monitor/performance")
def monitor_performance(
    source: str = "evaluation",
    model_version: str | None = None,
):
    try:
        return performance_report(
            source=source,
            model_version=model_version,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

@app.post('/monitor/drift')
def monitor_drift(payload: DriftPayload):
    try:
        reference = pd.DataFrame([row.to_features() for row in payload.reference])
        current = pd.DataFrame([row.to_features() for row in payload.current])
        return drift_report(reference,current)
    except ValueError as exc:
        raise HTTPException(status_code=422,detail=str(exc)) from exc

@app.get('/monitor/recent')
def monitor_recent(limit: int = 100):
    if not 1 <= limit <= 1000:
        raise HTTPException(status_code=422,detail='limit must be between 1 and 1000')
    return recent_predictions(limit)

# Editorial browser frontend, served from this same FastAPI origin.
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
_FRONTEND = Path(__file__).resolve().parents[1] / "frontend"
app.mount("/assets", StaticFiles(directory=_FRONTEND), name="frontend-assets")

@app.get("/", include_in_schema=False)
def dashboard_home():
    return FileResponse(_FRONTEND / "index.html")
