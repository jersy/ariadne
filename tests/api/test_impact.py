"""Tests for impact analysis endpoint."""

def test_impact_analysis(api_client, sample_db):
    """Test impact analysis."""
    # Add necessary data
    sample_db.conn.execute(
        """
        INSERT INTO symbols (fqn, kind, name, file_path)
        VALUES ('com.example.UserService.update', 'method', 'update', '/src/UserService.java'),
               ('com.example.UserController.update', 'method', 'update', '/src/UserController.java')
        """
    )
    sample_db.conn.execute(
        """
        INSERT INTO edges (from_fqn, to_fqn, relation)
        VALUES ('com.example.UserController.update', 'com.example.UserService.update', 'calls')
        """
    )
    sample_db.conn.commit()

    response = api_client.get(
        "/knowledge/impact",
        params={"target": "com.example.UserService.update", "depth": 3},
    )
    assert response.status_code == 200
    data = response.json()
    assert "target" in data
    assert "affected_callers" in data
    assert "risk_level" in data
    assert "confidence" in data


def test_impact_analysis_symbol_not_found(api_client, sample_db):
    """Test impact analysis with non-existent symbol."""
    response = api_client.get(
        "/knowledge/impact",
        params={"target": "com.example.NonExistent"},
    )
    assert response.status_code == 404
