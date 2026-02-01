"""Tests for search endpoint."""

def test_search_keyword(api_client, sample_db):
    """Test keyword search."""
    response = api_client.get("/knowledge/search?query=User")
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert "total" in data
    assert data["total"] >= 0


def test_search_with_results(api_client, sample_db):
    """Test search with actual results."""
    # First, add a summary for testing
    sample_db.conn.execute(
        """
        INSERT INTO summaries (target_fqn, level, summary)
        VALUES ('com.example.UserService', 'class', 'User management service')
        """
    )
    sample_db.conn.commit()

    response = api_client.get("/knowledge/search?query=UserService")
    assert response.status_code == 200
    data = response.json()
    assert "results" in data


def test_search_invalid_params(api_client, sample_db):
    """Test search with invalid parameters."""
    # num_results exceeds maximum
    response = api_client.get("/knowledge/search?query=test&num_results=200")
    # Should return validation error
    assert response.status_code == 422
