"""Integration tests for the FastAPI scoring API."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    """Create a test client with the FastAPI app.

    This fixture will work even without trained models;
    the health endpoint does not require models.
    """
    from credit_scoring.serving.api import create_app

    app = create_app()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_headers():
    return {"X-API-Key": "dev-api-key-change-in-production"}


class TestHealthEndpoint:
    def test_health_no_auth(self, client):
        """Health endpoint should not require auth."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "uptime_seconds" in data


class TestAuthMiddleware:
    def test_missing_api_key_returns_401(self, client):
        response = client.post("/api/v1/score", json={})
        assert response.status_code == 401

    def test_wrong_api_key_returns_401(self, client):
        response = client.post(
            "/api/v1/score",
            json={},
            headers={"X-API-Key": "wrong-key"},
        )
        assert response.status_code == 401


class TestScoringEndpoint:
    def test_missing_fields_returns_422(self, client, auth_headers):
        """Missing required fields should return 422."""
        response = client.post(
            "/api/v1/score",
            json={"application_id": "test"},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_valid_request_format(self, client, auth_headers, sample_scoring_request):
        """A well-formed request should not return 422.

        It may return 500 if models are not loaded, but the schema
        validation layer should pass.
        """
        response = client.post(
            "/api/v1/score",
            json=sample_scoring_request,
            headers=auth_headers,
        )
        # Either succeeds (200), models unavailable (503), or internal error (500)
        # Should NOT fail at validation (422)
        assert response.status_code != 422

    def test_batch_missing_fields_returns_422(self, client, auth_headers):
        response = client.post(
            "/api/v1/batch-score",
            json={"applications": [{"application_id": "x"}]},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_age_validation(self, client, auth_headers, sample_scoring_request):
        """Age below 18 should fail validation."""
        payload = sample_scoring_request.copy()
        payload["age"] = 10
        response = client.post(
            "/api/v1/score",
            json=payload,
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_negative_income_validation(self, client, auth_headers, sample_scoring_request):
        """Negative income should fail validation."""
        payload = sample_scoring_request.copy()
        payload["annual_income"] = -1000
        response = client.post(
            "/api/v1/score",
            json=payload,
            headers=auth_headers,
        )
        assert response.status_code == 422
