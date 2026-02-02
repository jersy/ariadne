"""Tests for glossary API endpoints."""

import pytest


class TestListGlossaryTerms:
    """Tests for GET /api/v1/knowledge/glossary"""

    def test_list_glossary_terms_default(self, api_client, sample_db):
        """Test listing all glossary terms with default parameters."""
        # Insert test glossary terms
        store = sample_db
        conn = store.conn
        conn.execute("""
            INSERT INTO glossary (code_term, business_meaning, synonyms)
            VALUES ('Sku', 'Stock Keeping Unit - 唯一标识一个可售卖的商品规格', '["规格", "商品SKU"]')
        """)
        conn.execute("""
            INSERT INTO glossary (code_term, business_meaning, synonyms)
            VALUES ('OrderId', '订单唯一标识符', '["订单号", "订单ID"]')
        """)
        conn.execute("""
            INSERT INTO glossary (code_term, business_meaning, synonyms)
            VALUES ('Spu', 'Standard Product Unit - 标准产品单位', '["产品单位", "SPU"]')
        """)
        conn.commit()

        response = api_client.get("/api/v1/knowledge/glossary")

        assert response.status_code == 200
        data = response.json()

        assert "terms" in data
        assert "total" in data
        assert data["total"] == 3
        assert len(data["terms"]) == 3

    def test_list_glossary_terms_with_pagination(self, api_client, sample_db):
        """Test pagination of glossary terms."""
        # Insert test data
        store = sample_db
        conn = store.conn
        conn.execute("""
            INSERT INTO glossary (code_term, business_meaning, synonyms)
            VALUES ('Test1', 'Test term 1', '[]')
        """)
        conn.execute("""
            INSERT INTO glossary (code_term, business_meaning, synonyms)
            VALUES ('Test2', 'Test term 2', '[]')
        """)
        conn.commit()

        response = api_client.get("/api/v1/knowledge/glossary?limit=1&offset=0")

        assert response.status_code == 200
        data = response.json()

        assert len(data["terms"]) == 1
        assert data["limit"] == 1
        assert data["offset"] == 0

    def test_list_glossary_terms_with_prefix_filter(self, api_client, sample_db):
        """Test filtering glossary terms by prefix."""
        store = sample_db
        conn = store.conn
        conn.execute("""
            INSERT INTO glossary (code_term, business_meaning, synonyms)
            VALUES ('Sku', 'Stock Keeping Unit', '["规格"]')
        """)
        conn.execute("""
            INSERT INTO glossary (code_term, business_meaning, synonyms)
            VALUES ('Spu', 'Standard Product Unit', '["SPU"]')
        """)
        conn.commit()

        response = api_client.get("/api/v1/knowledge/glossary?prefix=Sk")

        assert response.status_code == 200
        data = response.json()

        # Should return Sku and Spu (both start with "Sk")
        assert data["total"] >= 1
        for term in data["terms"]:
            assert term["code_term"].startswith("Sk")

    def test_list_glossary_terms_empty_prefix(self, api_client, sample_db):
        """Test with prefix that matches no terms."""
        response = api_client.get("/api/v1/knowledge/glossary?prefix=NonExistent")

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 0
        assert data["terms"] == []


class TestGetGlossaryTerm:
    """Tests for GET /api/v1/knowledge/glossary/{code_term}"""

    def test_get_existing_glossary_term(self, api_client, sample_db):
        """Test getting an existing glossary term."""
        store = sample_db
        conn = store.conn
        conn.execute("""
            INSERT INTO glossary (code_term, business_meaning, synonyms)
            VALUES ('Sku', 'Stock Keeping Unit', '["规格"]')
        """)
        conn.commit()

        response = api_client.get("/api/v1/knowledge/glossary/Sku")

        assert response.status_code == 200
        data = response.json()

        assert data["code_term"] == "Sku"
        assert "business_meaning" in data
        assert "synonyms" in data
        assert len(data["synonyms"]) >= 1

    def test_get_nonexistent_glossary_term(self, api_client):
        """Test getting a non-existent glossary term returns 404."""
        response = api_client.get("/api/v1/knowledge/glossary/NonExistent")

        assert response.status_code == 404


class TestSearchGlossary:
    """Tests for GET /api/v1/knowledge/glossary/search/{query}"""

    def test_search_glossary_by_code_term(self, api_client, sample_db):
        """Test searching glossary by code term."""
        store = sample_db
        conn = store.conn
        conn.execute("""
            INSERT INTO glossary (code_term, business_meaning, synonyms)
            VALUES ('Sku', 'Stock Keeping Unit', '["规格"]')
        """)
        conn.commit()

        response = api_client.get("/api/v1/knowledge/glossary/search/Sk")

        assert response.status_code == 200
        data = response.json()

        assert "query" in data
        assert data["query"] == "Sk"
        assert "results" in data
        assert data["num_results"] >= 1

        # Should find Sku
        sku_found = any(t["code_term"] == "Sku" for t in data["results"])
        assert sku_found

    def test_search_glossary_by_meaning(self, api_client, sample_db):
        """Test searching glossary by business meaning."""
        store = sample_db
        conn = store.conn
        conn.execute("""
            INSERT INTO glossary (code_term, business_meaning, synonyms)
            VALUES ('OrderId', '订单唯一标识符', '["订单号"]')
        """)
        conn.commit()

        response = api_client.get("/api/v1/knowledge/glossary/search/订单")

        assert response.status_code == 200
        data = response.json()

        assert data["query"] == "订单"
        assert "results" in data
        assert data["num_results"] >= 1

        # Should find OrderId
        order_found = any(t["code_term"] == "OrderId" for t in data["results"])
        assert order_found

    def test_search_glossary_no_results(self, api_client):
        """Test searching with query that matches nothing."""
        response = api_client.get("/api/v1/knowledge/glossary/search/XYZ123NonExistent")

        assert response.status_code == 200
        data = response.json()

        assert data["query"] == "XYZ123NonExistent"
        assert data["results"] == []
        assert data["num_results"] == 0
