"""Tests for graph query endpoint."""

def test_graph_query_outgoing(api_client, sample_db):
    """Test graph query with outgoing direction."""
    # Add necessary symbols and edges
    sample_db.conn.execute(
        """
        INSERT INTO symbols (fqn, kind, name, file_path)
        VALUES ('com.example.UserController.login', 'method', 'login', '/src/UserController.java'),
               ('com.example.UserService.login', 'method', 'login', '/src/UserService.java')
        """
    )
    sample_db.conn.execute(
        """
        INSERT INTO edges (from_fqn, to_fqn, relation)
        VALUES ('com.example.UserController.login', 'com.example.UserService.login', 'calls')
        """
    )
    sample_db.conn.commit()

    response = api_client.post(
        "/knowledge/graph/query",
        json={
            "start": "com.example.UserController.login",
            "direction": "outgoing",
            "depth": 2,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data
    assert "edges" in data
    assert "metadata" in data


def test_graph_query_symbol_not_found(api_client, sample_db):
    """Test graph query with non-existent symbol."""
    response = api_client.post(
        "/knowledge/graph/query",
        json={
            "start": "com.example.NonExistent",
            "direction": "outgoing",
            "depth": 1,
        },
    )
    assert response.status_code == 404


def test_graph_query_invalid_depth(api_client, sample_db):
    """Test graph query with invalid depth."""
    response = api_client.post(
        "/knowledge/graph/query",
        json={
            "start": "com.example.UserService",
            "direction": "outgoing",
            "depth": 50,  # Exceeds max of 20
        },
    )
    assert response.status_code == 422
