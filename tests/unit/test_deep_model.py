"""Tests for TensorFlow Wide & Deep PD model."""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest


class TestTensorFlowPDModel:
    """Test the TensorFlow Wide & Deep model."""

    @pytest.fixture(scope="class")
    def tf_model(self, train_test_data):
        try:
            from credit_scoring.models.deep_model import TensorFlowPDModel
        except ImportError:
            pytest.skip("TensorFlow not installed")

        X_train, _, y_train, _ = train_test_data
        model = TensorFlowPDModel(
            embedding_dim=8,
            dense_layers=[32, 16],
            dropout_rate=0.2,
            learning_rate=0.01,
            batch_size=64,
            epochs=5,
            early_stopping_patience=3,
        )
        model.fit(X_train, y_train)
        return model

    def test_model_builds(self, tf_model):
        """Model should build and have a Keras model."""
        assert tf_model.model is not None

    def test_predict_proba_shape(self, tf_model, train_test_data):
        _, X_test, _, _ = train_test_data
        proba = tf_model.predict_proba(X_test)
        assert proba.shape == (len(X_test), 2)

    def test_predict_pd_range(self, tf_model, train_test_data):
        _, X_test, _, _ = train_test_data
        pds = tf_model.predict_pd(X_test)
        assert (pds >= 0).all() and (pds <= 1).all()

    def test_probabilities_sum_to_one(self, tf_model, train_test_data):
        _, X_test, _, _ = train_test_data
        proba = tf_model.predict_proba(X_test)
        row_sums = proba.sum(axis=1)
        np.testing.assert_array_almost_equal(row_sums, np.ones(len(X_test)), decimal=5)

    def test_save_load_roundtrip(self, tf_model, train_test_data):
        from credit_scoring.models.deep_model import TensorFlowPDModel

        _, X_test, _, _ = train_test_data
        original_pds = tf_model.predict_pd(X_test)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tf_model"
            tf_model.save(path)
            loaded = TensorFlowPDModel.load(path)

        loaded_pds = loaded.predict_pd(X_test)
        np.testing.assert_array_almost_equal(original_pds, loaded_pds, decimal=4)

    def test_get_embeddings(self, tf_model, train_test_data):
        """Embedding extraction should return a 2D array."""
        _, X_test, _, _ = train_test_data
        embeddings = tf_model.get_embeddings(X_test)
        assert embeddings.ndim == 2
        assert embeddings.shape[0] == len(X_test)
        assert embeddings.shape[1] > 0
