# Credit Scoring Platform

Production credit risk assessment system with PD/LGD/EAD modeling, real-time scoring API, A/B testing, SHAP explainability, fairness monitoring, and drift detection.

## Architecture

```
                    +-------------------+
                    |   FastAPI Server   |
                    |  (scoring, auth,   |
                    |   rate limiting)   |
                    +---------+---------+
                              |
              +---------------+---------------+
              |               |               |
     +--------v--+   +-------v-----+  +------v------+
     | Feature    |   | Model       |  | Monitoring  |
     | Engineer   |   | Ensemble    |  | (Drift,     |
     | (63        |   | PD/LGD/EAD  |  |  Fairness,  |
     |  features) |   | Fraud       |  |  Prometheus)|
     +--------+---+   +-------+-----+  +------+------+
              |               |               |
     +--------v---+   +-------v-----+  +------v------+
     | Feature     |   | SHAP        |  | PostgreSQL  |
     | Store       |   | Explainer + |  | + Redis     |
     | (Parquet +  |   | Adverse     |  |             |
     |  Redis)     |   | Action      |  |             |
     +-------------+   +-------------+  +-------------+
```

## Models

| Model | Algorithm | Purpose |
|-------|-----------|---------|
| PD Logistic | Logistic Regression with StandardScaler | Baseline, interpretable |
| PD XGBoost | XGBClassifier with Optuna tuning | Primary tree model |
| PD LightGBM | LGBMClassifier with class imbalance handling | Fast gradient boosting |
| PD TensorFlow | Wide & Deep neural network | Captures nonlinear interactions |
| PD Ensemble | Weighted average (Nelder-Mead optimized) | Combined prediction |
| LGD | Two-stage: LogisticRegression + XGBRegressor | Loss severity on default |
| EAD | ML-predicted CCF with regulatory fallback | Exposure at default |
| Fraud | LGBMClassifier with imbalance handling | Fraud detection |

The PD ensemble combines base models with weights optimized on validation AUC via Nelder-Mead. Current weights: XGBoost 95.7%, Logistic 4.3%, LightGBM <0.1%.

### TensorFlow Wide & Deep

The deep model uses the Keras Functional API:

- **Wide path**: selected cross-product features through a single dense layer
- **Deep path**: BatchNormalization on numeric inputs, dense layers (256 > 128 > 64) with dropout
- **Training**: Adam optimizer, binary crossentropy with class weights, early stopping on validation AUC, ReduceLROnPlateau
- **Calibration**: post-training temperature scaling for well-calibrated probabilities
- **Persistence**: SavedModel format with metadata JSON

### Credit Score Mapping

PD values are mapped to a 300-850 scale using a calibrated logit transform. Risk tiers:

- **Low**: PD < 0.05
- **Medium**: PD 0.05-0.15
- **High**: PD 0.15-0.30
- **Very High**: PD > 0.30

Expected loss: `ECL = PD * LGD * EAD`

## Data

Two data paths, both produce the same 23-column borrower schema:

1. **Kaggle "Give Me Some Credit"**: 150k real borrowers with actual default labels (`SeriousDlqin2yrs`). Subsampled to 30k for training. Transaction and payment histories are synthetically enriched.
2. **Fully synthetic**: Gaussian copula for correlated borrower profiles with transaction and payment history generation. Falls back to this when Kaggle data is unavailable.

Synthetic borrower generation uses a Gaussian copula with an 8x8 correlation matrix across (age, income, credit limit, utilization, DTI, employment length, delinquencies, account age). Default labels come from a latent logistic model with intercept calibration via Brent's method to hit the target default rate.

Transaction and payment enrichment uses observable credit features (DTI, utilization, delinquencies) to drive behavioral variation, not the default label, to prevent target leakage.

## Feature Engineering

63 features across 8 groups:

| Group | Examples |
|-------|----------|
| Demographic | age, log_annual_income, employment_length, account_age |
| Credit | utilization_ratio, existing_lines, delinquencies, DTI |
| Velocity | txn_count_{7d,30d,90d}, amount_sum, decline_rate |
| Aggregation | avg_spend_by_category, merchant_diversity, spend_entropy |
| Behavioral | mobile_fraction, weekend_fraction, nighttime_fraction |
| Time Series | spend_trend_{3m,6m}, volatility, frequency_trend |
| Payment | on_time_rate, avg_days_past_due, consecutive_on_time, payment_trend |
| Risk Ratios | loan_to_income, balance_to_income, utilization_x_dti |

Categorical encoding: one-hot for low-cardinality (employment_type, home_ownership, loan_purpose, device_type), target encoding for state.

## A/B Testing (Shadow Mode)

The scoring API supports shadow mode for safe model comparison in production:

- **Champion** (ensemble) scores every request and drives the decision
- **Challenger** (e.g., XGBoost-only) scores the same request silently
- Results are logged and compared via `/api/v1/shadow/report`
- Tracks decision agreement rate, PD correlation, latency difference, and promotion readiness

## Explainability

**SHAP**: TreeExplainer for tree-based models, DeepExplainer for TensorFlow. Provides global feature importance and per-prediction contribution breakdowns.

**Adverse Action Codes**: 20 ECOA-compliant reason codes (AA001-AA020) mapped from features. The system selects the top 4 risk-increasing features per prediction, excluding protected attributes (age).

## Fairness

Three metrics computed across protected groups:

- **Demographic Parity**: approval rates should differ by less than 10%
- **Equalized Odds**: TPR and FPR should be comparable across groups
- **Disparate Impact Ratio**: must meet the 4/5 rule (ratio >= 0.80)

BiasMonitor tracks these over time and flags degradation.

## Monitoring

- **Data Drift**: PSI per feature (< 0.10 stable, 0.10-0.25 warning, > 0.25 alert)
- **Performance Tracking**: batch-level AUC/KS monitoring over time
- **Prometheus Metrics**: request count, latency histogram, model AUC gauge, drift PSI, fairness disparity

Run the drift monitoring demo:
```bash
python scripts/drift_demo.py
```

## Quickstart

### Install

```bash
pip install -e ".[dev]"
```

### Generate Data

```bash
# Option 1: Download Kaggle dataset (requires kaggle CLI credentials)
python scripts/download_data.py

# Option 2: Generate fully synthetic data
make generate-data
```

### Train

```bash
make train
```

Runs the full pipeline: data loading, validation, feature engineering, Optuna hyperparameter tuning, model training (LR, XGBoost, LightGBM), ensemble optimization, LGD/EAD/Fraud training, evaluation, and MLflow logging.

Output goes to `models/` (joblib files for tree models, SavedModel directory for TensorFlow).

### Serve

```bash
make serve
```

Starts the FastAPI server on port 8000 with all models loaded.

### Test

```bash
make test
```

### Lint

```bash
make lint
```

## Docker

```bash
# Start all services (PostgreSQL, Redis, MLflow, Prometheus, API)
make docker-up

# Stop
make docker-down
```

Services:
- PostgreSQL 16 on port 5432
- Redis 7 on port 6379
- MLflow on port 5000
- Prometheus on port 9090
- API on port 8000

## API Reference

All endpoints except `/health` require the `X-API-Key` header.

### POST /api/v1/score

Score a single credit application.

Request:
```json
{
  "application_id": "app-001",
  "borrower_id": "b-001",
  "age": 35,
  "annual_income": 75000,
  "employment_length_years": 8,
  "employment_type": "employed",
  "home_ownership": "mortgage",
  "existing_credit_lines": 5,
  "total_credit_limit": 50000,
  "current_credit_balance": 15000,
  "months_since_last_delinquency": null,
  "number_of_delinquencies": 0,
  "debt_to_income_ratio": 0.25,
  "requested_loan_amount": 20000,
  "loan_purpose": "debt_consolidation",
  "state": "CA",
  "account_age_months": 120,
  "profile_completeness_score": 0.95,
  "device_type": "desktop"
}
```

Response:
```json
{
  "application_id": "app-001",
  "credit_score": 745,
  "risk_tier": "low",
  "probability_of_default": 0.043,
  "loss_given_default": 0.22,
  "exposure_at_default": 601.52,
  "expected_loss": 5.81,
  "fraud_score": 0.001,
  "fraud_flag": false,
  "decision": "approved",
  "adverse_action_reasons": null,
  "scored_at": "2026-02-19T13:01:54Z",
  "model_version": "1.0.0"
}
```

### POST /api/v1/batch-score

Score multiple applications in one request. Same request fields as single scoring, wrapped in an `applications` array.

### POST /api/v1/score/{application_id}/explanation

Get SHAP feature contributions and adverse action reason codes for a scored application.

### GET /api/v1/shadow/report

Get A/B comparison report between champion and challenger models.

### GET /api/v1/shadow/recent

Get recent shadow comparison results with per-request detail.

### GET /api/v1/health

System health check. No auth required.

### GET /api/v1/metrics

Operational and model performance metrics (request count, latency, AUC, drift).

## Configuration

YAML files in `configs/`:

- `data.yaml`: borrower count, default/fraud rates, data paths
- `model.yaml`: model types, Optuna trials, CV folds, AUC threshold, deep model hyperparameters
- `serving.yaml`: host, port, workers, API key, rate limits

Environment variables override YAML values. See `.env.example` for available overrides.

## Project Structure

```
src/credit_scoring/
  config/          Configuration and settings
  data/            Data download, synthetic generation, validation
  features/        Feature engineering, registry, store
  models/          PD, LGD, EAD, Fraud models, ensemble, training
  explainability/  SHAP, adverse action codes, fairness
  serving/         FastAPI app, routes, middleware, schemas, shadow mode
  monitoring/      Drift detection, performance tracking, Prometheus
  utils/           Logging, database
```

## CI/CD

GitHub Actions workflows:

- **ci.yml**: runs on push/PR to main. Lints with ruff, runs all tests.
- **train.yml**: weekly scheduled training pipeline. Generates data, trains models, uploads artifacts.

## Results

Trained on 30k borrowers from Kaggle "Give Me Some Credit" dataset (6.5% default rate):

| Model | AUC | KS | Gini |
|-------|-----|-----|------|
| XGBoost | 0.8795 | 0.6184 | 0.7590 |
| Logistic Regression | 0.8642 | 0.5742 | 0.7283 |
| LightGBM | 0.8356 | 0.5335 | 0.6712 |
| **Ensemble** | **0.8789** | **0.6115** | **0.7578** |
