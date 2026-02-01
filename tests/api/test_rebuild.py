"""Tests for rebuild and jobs endpoints."""

import time


def test_trigger_rebuild_async(api_client, sample_db):
    """Test triggering an async rebuild."""
    # Set project root to avoid errors
    import os
    os.environ["ARIADNE_PROJECT_ROOT"] = "/tmp"

    response = api_client.post(
        "/knowledge/rebuild",
        json={
            "mode": "incremental",
            "async": True,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert "status" in data
    assert data["status"] in ["pending", "running"]


def test_get_job_status(api_client, sample_db):
    """Test getting job status."""
    # First trigger a rebuild
    import os
    os.environ["ARIADNE_PROJECT_ROOT"] = "/tmp"

    rebuild_response = api_client.post(
        "/knowledge/rebuild",
        json={"mode": "incremental", "async": True},
    )
    job_id = rebuild_response.json()["job_id"]

    # Get job status
    response = api_client.get(f"/jobs/{job_id}")
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert data["job_id"] == job_id
    assert "status" in data


def test_get_nonexistent_job(api_client, sample_db):
    """Test getting status of non-existent job."""
    response = api_client.get("/jobs/nonexistent-job-id")
    assert response.status_code == 404


def test_list_jobs(api_client, sample_db):
    """Test listing jobs."""
    response = api_client.get("/jobs")
    assert response.status_code == 200
    data = response.json()
    assert "jobs" in data
