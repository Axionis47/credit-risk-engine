# Held-out evaluation evidence

`heldout_metrics.json` is produced by `scripts/evaluate.py` (run 2026-07-15) against the saved
model artifacts, on the exact 65/15/20 stratified split training used (random_state=42, fully
deterministic). PD labels are the real Kaggle "Give Me Some Credit" outcomes, 150,000 borrowers
subsampled to 30,000; the data and model artifacts themselves are gitignored, but the split is
reconstructible and these metrics are reproducible from them.

Held-out test AUC (6,000 rows): Logistic 0.8642, XGBoost 0.8795, LightGBM 0.8332,
Ensemble 0.8794.

For the record: an earlier version of `evaluate.py` scored the full dataset including the
19,500 training rows, which printed LightGBM at 0.9418. That number was train-contaminated,
and the Nelder-Mead ensemble weights (fit on validation, where LightGBM scores 0.8017) had
already assigned it 0.004% weight. The numbers in this directory are the ones I stand behind.
