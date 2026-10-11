# DriftLab — Architecture and Engineering Decisions

## 1. Problem and scope

The goal is to explore the lifecycle of a classification model for machine-failure prediction: dataset preparation, validation, artifact packaging, web inference, data monitoring, candidate evaluation, and operational safeguards.

The project is educational. It does not diagnose a real machine or guarantee safety.

## 2. Dataset and model inputs

The AI4I 2020 dataset has 10,000 examples and 339 positive machine-failure labels. We retain six operational features: Type; air temperature; process temperature; rotational speed; torque; and tool wear. We exclude record/product IDs and outcome-derived failure-type labels to avoid leaking information into the model.

A stratified train/validation/test split preserves the rare positive class more consistently across partitions. The train set is used for fitting; validation guides threshold and candidate decisions; the held-out test set should not be repeatedly reused for selection.

## 3. Training architecture

`DriftLab.ipynb` contains EDA, preprocessing and model experiments. The modeling work includes Logistic Regression, Random Forest, and a PyTorch MLP. Categorical machine type requires encoding; numeric features require consistent treatment appropriate to the selected model. The exported model and preprocessing must remain coupled.

Model outputs are probabilities. A chosen threshold (currently 0.30 for deployed v1) maps probability to failure/no-failure prediction. Because failures are relatively rare, use recall, precision, F1, and average precision to discuss model quality.

## 4. Serving architecture

A FastAPI app exposes `/predict`, model metadata, and `/health`. Its prediction layer loads the active model artifact from the versioned registry. The API maps the six browser input names to the original model feature names and attaches a prediction ID to each recorded inference.

The browser frontend is static HTML/CSS/JavaScript served from the same application. This avoids a second frontend service for the local demo.

## 5. Persistence and provenance

SQLite stores prediction timestamp, version, sensor reading, probability, decision, outcome (when known), and source. Sources include evaluation, simulation, production, and legacy_unverified. Public dashboard submissions are evaluation data, not verified production observations. The performance report can filter by source and model version.

A known outcome should be recorded only when ground truth is available. An unlabelled prediction cannot be assumed correct or negative.

## 6. Drift monitoring

The drift endpoint compares two batches of six input features. It uses population stability index for numeric features and total variation distance for machine type. Results can be stored in a separate drift-history table, including model version, sample sizes, flagged feature count, and a declared simulation marker.

The frontend visualizes the distributions and scores. Histogram bins shown in the UI are illustrative and need not coincide with backend PSI binning. A shift in the input distribution is a signal for investigation, not proof of deterioration in predictive accuracy.

## 7. Challenger training and governance

The training script fits a challenger offline and evaluates it on the same validation partition used to compare with the champion. It saves a new version without switching the active version. Its screening rule requires strictly higher average precision and recall no worse than the champion; human review remains necessary.

The actual recorded comparison: v1 AP 0.7285, recall 0.7255, precision 0.7872, F1 0.7551; v2 AP 0.7249, recall 0.7059, precision 0.6316, F1 0.6667. v2 failed screening and v1 remains active.

Protected model-management endpoints require an administrator key. Registry activation uses a Linux file lock, checks current active version while locked, validates model artifacts, and atomically replaces the active pointer. Isolated tests exercise promotion, rollback, and racing requests. This is not a full distributed model registry.

## 8. Environment and deployment

Local development uses WSL Linux because Windows Application Control prevented SciPy binary extensions from importing. A second failure demonstrated that the model's serialized scikit-learn internals require compatible dependency versions. The project now has a frozen working-environment package list and local Docker Compose configuration.

Docker binds `models/` and `data/` so local artifacts and SQLite records remain outside the image. The dashboard and API share the same origin. Avoid exposing the local registry publicly without stronger security and operational review.

## 9. Key engineering lessons

- The input contract and leakage rules are as important as the model algorithm.
- A notebook validation score cannot guarantee correct API inference.
- Model artifacts include preprocessing, thresholds, and runtime compatibility.
- Monitoring requires data provenance and known labels.
- A changed sensor distribution is not equivalent to model failure.
- A challenger can be validly trained but still be rejected.
- File locks and atomic replacement help, but do not make multi-file updates crash-transactional.

## 10. Explicit limitations

No live industrial data source, external alerting, automated retraining scheduler, statistically powered monitoring system, or fully transactional registry has been demonstrated. Current deployment is local; it should not be represented as a production-certified industrial monitoring system.
