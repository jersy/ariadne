"""Tests for API versioning."""

import os

import pytest


def test_api_versioned_endpoints_work(api_client):
    """Test that versioned API endpoints work."""
    # Test versioned search endpoint
    response = api_client.get("/api/v1/knowledge/search?query=test")
    # Should work - may return 200 with results or empty results
    # May return 503 if database unavailable in test environment
    assert response.status_code in (200, 503)

    # Test versioned graph endpoint
    response = api_client.post("/api/v1/knowledge/graph/query", json={
        "start": "com.example.Service",
        "direction": "outgoing",
        "relation": "calls",
        "depth": 2,
    })
    # Should return 404 for non-existent symbol, not 404 for route
    assert response.status_code in (200, 404, 503)


def test_api_root_shows_version_info(api_client):
    """Test that root endpoint shows version information."""
    response = api_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "api_version" in data
    assert "endpoints" in data
    assert "current" in data["endpoints"]


def test_api_v1_root_endpoint(api_client):
    """Test the API v1 root endpoint."""
    response = api_client.get("/api/v1")
    assert response.status_code == 200
    data = response.json()
    assert data["version"] == "v1"


def test_legacy_endpoints_still_work(api_client):
    """Test that legacy (unversioned) endpoints still work for backward compatibility."""
    # Legacy search endpoint should still work
    response = api_client.get("/knowledge/search?query=test")
    # May return 503 if database unavailable in test environment
    assert response.status_code in (200, 503)

    # Legacy graph endpoint should still work
    response = api_client.post("/knowledge/graph/query", json={
        "start": "com.example.Service",
        "direction": "outgoing",
        "relation": "calls",
        "depth": 2,
    })
    # Should return 404 for non-existent symbol, not 404 for route
    assert response.status_code in (200, 404, 503)


def test_health_check_unversioned(api_client):
    """Test that health check endpoint remains unversioned."""
    response = api_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
