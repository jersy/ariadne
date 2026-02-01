"""Tests for constraints and check endpoints."""

def test_get_constraints(api_client, sample_db):
    """Test getting constraints."""
    # Add a test constraint
    sample_db.conn.execute(
        """
        INSERT INTO constraints (name, description)
        VALUES ('test_constraint', 'Test constraint description')
        """
    )
    sample_db.conn.commit()

    response = api_client.get("/knowledge/constraints")
    assert response.status_code == 200
    data = response.json()
    assert "constraints" in data
    assert "anti_patterns" in data


def test_check_code(api_client, sample_db):
    """Test live code check."""
    response = api_client.post(
        "/knowledge/check",
        json={
            "changes": [
                {
                    "file": "/src/Example.java",
                    "added_symbols": ["com.example.NewClass"],
                }
            ]
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "violations" in data
    assert "warnings" in data
