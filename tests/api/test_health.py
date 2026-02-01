"""Tests for health check endpoint."""

import os


def test_health_check_no_database(api_client):
    """Test health check when database doesn't exist."""
    # Remove database path
    if "ARIADNE_DB_PATH" in os.environ:
        del os.environ["ARIADNE_DB_PATH"]

    response = api_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "services" in data


def test_health_check_with_database(api_client, sample_db):
    """Test health check with database."""
    response = api_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "services" in data
    assert "database" in data["services"]
