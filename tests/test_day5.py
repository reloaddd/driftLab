import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import pandas as pd
from src.driftlab.monitoring import drift_report
from src.driftlab.storage import log_prediction, store_outcome, performance_report
from src.driftlab.schema import FEATURES

def fake_frame(n=100, shift=0):
    return pd.DataFrame({'Type':['L','M']*(n//2), 'Air temperature [K]':[300+i%5 for i in range(n)],
      'Process temperature [K]':[310+i%5 for i in range(n)],'Rotational speed [rpm]':[1300+i%10 for i in range(n)],
      'Torque [Nm]':[40+i%10+shift for i in range(n)],'Tool wear [min]':[i for i in range(n)]})

def test_drift_returns_flags():
    report=drift_report(fake_frame(),fake_frame(shift=20))
    assert 'Torque [Nm]' in report['flagged_features']
    assert 'Type' in report['features']

def test_requires_enough_samples():
    try: drift_report(fake_frame(20),fake_frame())
    except ValueError: return
    raise AssertionError('Expected ValueError')

def test_prediction_lifecycle(tmp_path):
    db=tmp_path/'test.sqlite'
    result={'model_version':'v1','failure_probability':0.8,'predicted_failure':1}
    id_=log_prediction({'Type':'L'},result,db)
    assert store_outcome(id_,1,db)
    assert not store_outcome(id_,0,db)
    assert performance_report(db)['status']=='insufficient_labels'
