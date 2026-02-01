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


def test_constraints_valid_severity(api_client, sample_db):
    """Test that valid severity values are accepted."""
    # First add a symbol that the anti_pattern can reference
    from ariadne_core.models.types import SymbolData, SymbolKind
    sample_db.insert_symbols([
        SymbolData(
            fqn="com.example.Test",
            kind=SymbolKind.CLASS,
            name="Test",
            file_path="/src/Test.java",
            line_number=1,
        ),
    ])

    # Add a test anti-pattern violation
    sample_db.conn.execute(
        """
        INSERT INTO anti_patterns (rule_id, from_fqn, severity, message, detected_at)
        VALUES ('test_rule', 'com.example.Test', 'error', 'Test violation', datetime('now'))
        """
    )
    sample_db.conn.commit()

    # Valid severity values should work
    for severity in ["error", "warning", "info", "critical"]:
        response = api_client.get(f"/knowledge/constraints?severity={severity}")
        assert response.status_code == 200, f"Severity {severity} should be valid"


def test_constraints_invalid_severity_rejected(api_client, sample_db):
    """Test that invalid severity values are rejected to prevent SQL injection."""
    # Attempt SQL injection via severity parameter
    malicious_inputs = [
        "error'; DROP TABLE anti_patterns; --",
        "error OR 1=1 --",
        "error' UNION SELECT * FROM symbols --",
        "'; DELETE FROM constraints WHERE '1'='1",
        "error' OR '1'='1",
    ]

    for malicious_input in malicious_inputs:
        response = api_client.get(f"/knowledge/constraints?severity={malicious_input}")
        assert response.status_code == 400, f"Malicious input should be rejected: {malicious_input}"
        assert "Invalid severity" in response.json()["detail"]


def test_constraints_sql_injection_in_context(api_client, sample_db):
    """Test that context parameter is safely handled (parameterized query)."""
    # Even with malicious input, parameterized queries should be safe
    malicious_context = "com.example' OR '1'='1"

    response = api_client.get(f"/knowledge/constraints?context={malicious_context}")
    # Should return 200 with empty results, not an error
    # The parameterized query treats this as a literal string, not SQL
    assert response.status_code == 200
    data = response.json()
    assert "anti_patterns" in data
