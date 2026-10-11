"""Explicit candidate evaluation and manual activation, not unattended promotion."""
from pathlib import Path
import json
import pandas as pd
from sklearn.metrics import average_precision_score, f1_score
from .registry import register, activate, model_dir

def compare_candidates(champion, challenger, X_val: pd.DataFrame, y_val, threshold_champion, threshold_challenger):
    """Both candidates receive the same held-out validation observations."""
    results={}
    for name, model, t in [('champion',champion,threshold_champion),('challenger',challenger,threshold_challenger)]:
        p=model.predict_proba(X_val)[:,1]
        results[name]={'average_precision':float(average_precision_score(y_val,p)),
                       'f1':float(f1_score(y_val,p>=t,zero_division=0)), 'threshold':float(t)}
    results['candidate_improves_ap']=results['challenger']['average_precision']>results['champion']['average_precision']
    results['note']='Evaluate on a fixed holdout and review errors; this check never auto-activates a model.'
    return results

def activate_reviewed_candidate(version, root=None):
    """Explicit, human-approved action. Call only after inspecting candidate results."""
    activate(version,root)
    from .prediction import load_model
    load_model.cache_clear()
