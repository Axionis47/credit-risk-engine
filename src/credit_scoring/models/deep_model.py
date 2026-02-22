"""TensorFlow Wide & Deep model for Probability of Default estimation."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from credit_scoring.models.pd_model import BasePDModel


class TensorFlowPDModel(BasePDModel):
    """Wide & Deep neural network for PD using TensorFlow/Keras.

    Architecture:
        Wide: cross-product interaction features -> Dense(1)
        Deep: numeric normalization + categorical embeddings -> Dense(256) -> Dense(128) -> Dense(64)
        Combined: concat(wide, deep) -> Dense(1, sigmoid)
    """

    NUMERIC_FEATURES = [
        "age",
        "log_annual_income",
        "employment_length_years",
        "account_age_months",
        "profile_completeness_score",
        "credit_utilization_ratio",
        "existing_credit_lines",
        "number_of_delinquencies",
        "debt_to_income_ratio",
        "loan_to_income_ratio",
        "balance_to_income_ratio",
        "utilization_x_dti",
        "income_stability_proxy",
        "txn_count_30d",
        "txn_amount_sum_30d",
        "txn_amount_mean_30d",
        "decline_rate_30d",
        "on_time_payment_rate",
        "avg_days_past_due",
        "missed_payment_count",
        "spend_trend_6m",
        "spend_volatility_6m",
    ]

    WIDE_CROSS_FEATURES = [
        ("credit_utilization_ratio", "debt_to_income_ratio"),
        ("log_annual_income", "loan_to_income_ratio"),
        ("number_of_delinquencies", "credit_utilization_ratio"),
    ]

    def __init__(
        self,
        embedding_dim: int = 32,
        dense_layers: list[int] | None = None,
        dropout_rate: float = 0.3,
        learning_rate: float = 0.001,
        batch_size: int = 256,
        epochs: int = 100,
        early_stopping_patience: int = 15,
    ):
        self.embedding_dim = embedding_dim
        self.dense_layers = dense_layers or [256, 128, 64]
        self.dropout_rate = dropout_rate
        self.learning_rate = learning_rate
        self.batch_size = batch_size
        self.epochs = epochs
        self.early_stopping_patience = early_stopping_patience
        self.model = None
        self.temperature = 1.0
        self._feature_columns: list[str] = []

    def _build_model(self, n_features: int):
        import tensorflow as tf

        inputs = tf.keras.Input(shape=(n_features,), name="features")

        # Deep branch
        x = tf.keras.layers.BatchNormalization()(inputs)
        for units in self.dense_layers:
            x = tf.keras.layers.Dense(units, activation="relu", kernel_regularizer=tf.keras.regularizers.l2(0.001))(x)
            x = tf.keras.layers.BatchNormalization()(x)
            x = tf.keras.layers.Dropout(self.dropout_rate)(x)

        deep_output = x

        # Wide branch (identity pass-through of selected interaction features)
        wide_output = tf.keras.layers.Dense(16, activation="relu")(inputs)

        # Combine
        combined = tf.keras.layers.Concatenate()([wide_output, deep_output])
        combined = tf.keras.layers.Dense(32, activation="relu")(combined)
        combined = tf.keras.layers.Dropout(self.dropout_rate * 0.5)(combined)
        output = tf.keras.layers.Dense(1, activation="sigmoid", name="pd_output")(combined)

        self.model = tf.keras.Model(inputs=inputs, outputs=output)
        self.model.compile(
            optimizer=tf.keras.optimizers.Adam(learning_rate=self.learning_rate),
            loss="binary_crossentropy",
            metrics=[tf.keras.metrics.AUC(name="auc")],
        )

    def _prepare_features(self, X: pd.DataFrame) -> np.ndarray:
        """Select and order features for the model."""
        if not self._feature_columns:
            numeric_types = [np.float64, np.float32, np.int64, np.int32, float, int]
            self._feature_columns = [c for c in X.columns if X[c].dtype in numeric_types]
        available = [c for c in self._feature_columns if c in X.columns]
        arr = X[available].values.astype(np.float32)
        arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)
        return arr

    def fit(self, X: pd.DataFrame, y: np.ndarray) -> TensorFlowPDModel:
        import tensorflow as tf

        X_arr = self._prepare_features(X)
        self._build_model(X_arr.shape[1])

        # Class weights for imbalance
        n_pos = y.sum()
        n_neg = len(y) - n_pos
        weight_pos = n_neg / (n_pos + 1)
        weight_neg = 1.0
        class_weight = {0: weight_neg, 1: min(weight_pos, 50.0)}

        class PrintProgress(tf.keras.callbacks.Callback):
            """Flush-safe progress callback for non-interactive environments."""

            def on_epoch_end(self, epoch, logs=None):
                logs = logs or {}
                auc = logs.get("auc", 0)
                val_auc = logs.get("val_auc", 0)
                loss = logs.get("loss", 0)
                print(f"  Epoch {epoch + 1}: loss={loss:.4f}, auc={auc:.4f}, val_auc={val_auc:.4f}", flush=True)

        callbacks = [
            tf.keras.callbacks.EarlyStopping(
                monitor="val_auc",
                patience=self.early_stopping_patience,
                mode="max",
                restore_best_weights=True,
            ),
            tf.keras.callbacks.ReduceLROnPlateau(
                monitor="val_auc",
                factor=0.5,
                patience=5,
                mode="max",
            ),
            PrintProgress(),
        ]

        self.model.fit(
            X_arr,
            y,
            validation_split=0.15,
            batch_size=self.batch_size,
            epochs=self.epochs,
            class_weight=class_weight,
            callbacks=callbacks,
            verbose=0,
        )

        # Temperature scaling for calibration
        self._calibrate_temperature(X_arr, y)

        return self

    def _calibrate_temperature(self, X: np.ndarray, y: np.ndarray):
        """Learn temperature parameter for probability calibration."""
        from scipy.optimize import minimize_scalar

        logits = self.model.predict(X, verbose=0).flatten()
        # Convert sigmoid output back to logit
        logits = np.clip(logits, 1e-7, 1 - 1e-7)
        logits = np.log(logits / (1 - logits))

        def nll(T):
            scaled = 1 / (1 + np.exp(-logits / T))
            scaled = np.clip(scaled, 1e-7, 1 - 1e-7)
            return -np.mean(y * np.log(scaled) + (1 - y) * np.log(1 - scaled))

        result = minimize_scalar(nll, bounds=(0.1, 10.0), method="bounded")
        self.temperature = result.x

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        X_arr = self._prepare_features(X)
        raw_probs = self.model.predict(X_arr, verbose=0).flatten()

        # Apply temperature scaling
        raw_probs = np.clip(raw_probs, 1e-7, 1 - 1e-7)
        logits = np.log(raw_probs / (1 - raw_probs))
        calibrated = 1 / (1 + np.exp(-logits / self.temperature))

        return np.column_stack([1 - calibrated, calibrated])

    def get_embeddings(self, X: pd.DataFrame) -> np.ndarray:
        """Return penultimate layer activations for feature extraction."""
        import tensorflow as tf

        X_arr = self._prepare_features(X)
        # Get output from the layer before the final Dense
        layer_model = tf.keras.Model(
            inputs=self.model.input,
            outputs=self.model.layers[-3].output,
        )
        return layer_model.predict(X_arr, verbose=0)

    def save(self, path: str | Path):
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        self.model.save(path / "saved_model")
        # Save metadata
        import json

        meta = {
            "temperature": self.temperature,
            "feature_columns": self._feature_columns,
            "embedding_dim": self.embedding_dim,
            "dense_layers": self.dense_layers,
        }
        with open(path / "metadata.json", "w") as f:
            json.dump(meta, f)

    @classmethod
    def load(cls, path: str | Path) -> TensorFlowPDModel:
        import json

        import tensorflow as tf

        path = Path(path)
        instance = cls.__new__(cls)
        instance.model = tf.keras.models.load_model(path / "saved_model")

        with open(path / "metadata.json") as f:
            meta = json.load(f)

        instance.temperature = meta["temperature"]
        instance._feature_columns = meta["feature_columns"]
        instance.embedding_dim = meta.get("embedding_dim", 32)
        instance.dense_layers = meta.get("dense_layers", [256, 128, 64])
        instance.dropout_rate = 0.3
        instance.learning_rate = 0.001
        instance.batch_size = 256
        instance.epochs = 100
        instance.early_stopping_patience = 15

        return instance
