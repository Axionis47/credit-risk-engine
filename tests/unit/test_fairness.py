"""Tests for fairness metrics."""

from __future__ import annotations

import numpy as np
import pytest

from credit_scoring.explainability.fairness import BiasMonitor, FairnessMetrics


class TestFairnessMetrics:

    @pytest.fixture
    def metrics(self):
        return FairnessMetrics(protected_attribute="group", favorable_outcome=0)

    def test_demographic_parity_equal_groups(self, metrics):
        """Equal approval rates should pass."""
        y_pred = np.array([0, 0, 1, 1, 0, 0, 1, 1])
        groups = np.array(["A", "A", "A", "A", "B", "B", "B", "B"])
        result = metrics.demographic_parity(y_pred, groups)
        assert result["max_disparity"] == 0.0
        assert result["passed"] is True

    def test_demographic_parity_unequal_groups(self, metrics):
        """Very different approval rates should flag disparity."""
        y_pred = np.array([0, 0, 0, 0, 1, 1, 1, 1])
        groups = np.array(["A", "A", "A", "A", "B", "B", "B", "B"])
        result = metrics.demographic_parity(y_pred, groups)
        assert result["max_disparity"] == 1.0
        assert result["passed"] is False

    def test_equalized_odds_structure(self, metrics):
        y_true = np.array([1, 0, 1, 0, 1, 0])
        y_pred = np.array([1, 0, 1, 0, 0, 1])
        groups = np.array(["A", "A", "A", "B", "B", "B"])

        result = metrics.equalized_odds(y_true, y_pred, groups)
        assert "tpr_by_group" in result
        assert "fpr_by_group" in result
        assert "tpr_disparity" in result
        assert "passed" in result

    def test_disparate_impact_four_fifths_rule(self, metrics):
        """Passing the 4/5 rule means ratio >= 0.80."""
        # Group A: 4/5 favorable, Group B: 3/5 favorable
        y_pred = np.array([0, 0, 0, 0, 1, 0, 0, 0, 1, 1])
        groups = np.array(["A", "A", "A", "A", "A", "B", "B", "B", "B", "B"])

        result = metrics.disparate_impact_ratio(y_pred, groups, "A")
        assert "min_ratio" in result
        assert isinstance(result["passed"], bool)

    def test_disparate_impact_perfect_equality(self, metrics):
        y_pred = np.array([0, 1, 0, 1])
        groups = np.array(["A", "A", "B", "B"])
        result = metrics.disparate_impact_ratio(y_pred, groups, "A")
        assert result["min_ratio"] == 1.0
        assert result["passed"] is True

    def test_compute_all_returns_all_metrics(self, metrics):
        y_true = np.array([1, 0, 1, 0, 1, 0])
        y_pred = np.array([1, 0, 0, 0, 1, 0])
        y_prob = np.array([0.8, 0.2, 0.6, 0.3, 0.7, 0.1])
        groups = np.array(["A", "A", "A", "B", "B", "B"])

        result = metrics.compute_all(y_true, y_pred, y_prob, groups, "A")
        assert "demographic_parity" in result
        assert "equalized_odds" in result
        assert "disparate_impact" in result


class TestBiasMonitor:

    def test_empty_history_no_warnings(self):
        monitor = BiasMonitor()
        assert monitor.check_degradation() == []

    def test_degradation_detected(self):
        monitor = BiasMonitor()
        monitor.record_metrics(
            {"demographic_parity": {"passed": True}}, "2024-01-01"
        )
        monitor.record_metrics(
            {"demographic_parity": {"passed": False}}, "2024-02-01"
        )
        warnings = monitor.check_degradation()
        assert len(warnings) > 0
        assert any("parity" in w.lower() for w in warnings)

    def test_no_degradation_when_passing(self):
        monitor = BiasMonitor()
        monitor.record_metrics(
            {"demographic_parity": {"passed": True}}, "2024-01-01"
        )
        monitor.record_metrics(
            {"demographic_parity": {"passed": True}}, "2024-02-01"
        )
        warnings = monitor.check_degradation()
        assert len(warnings) == 0
