from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from fastapi.testclient import TestClient
from api.main import app
from src.driftlab.schema import SensorReading

SAMPLE = {
    'machine_type': 'L', 'air_temperature': 302.5, 'process_temperature': 312.8,
    'rotational_speed': 1420, 'torque': 48.2, 'tool_wear': 180
}

def test_feature_mapping():
    features = SensorReading(**SAMPLE).to_features()
    assert features['Type'] == 'L'
    assert features['Torque [Nm]'] == 48.2
    assert len(features) == 6

def test_invalid_category_rejected():
    response = TestClient(app).post('/predict', json={**SAMPLE, 'machine_type':'UNKNOWN'})
    assert response.status_code == 422

def test_unexpected_field_rejected():
    response = TestClient(app).post('/predict', json={**SAMPLE, 'Machine failure': 1})
    assert response.status_code == 422

def test_health_endpoint():
    assert TestClient(app).get('/health').status_code == 200
