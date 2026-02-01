"""Glossary API endpoints for domain vocabulary access."""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ariadne_api.dependencies import get_store
from ariadne_api.schemas.glossary import (
    GlossarySearchResponse,
    GlossaryTerm,
    GlossaryTermList,
)

router = APIRouter(prefix="/glossary")
logger = logging.getLogger(__name__)


@router.get("", response_model=GlossaryTermList, tags=["glossary"])
async def list_glossary_terms(
    prefix: str = Query(None, description="Filter by code_term prefix"),
    limit: int = Query(100, ge=1, le=1000, description="Max results (1-1000)"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> GlossaryTermList:
    """List all domain glossary terms.

    Returns domain vocabulary mapping code terms to business meanings.
    This is a core L1 feature that helps agents understand business context.
    """
    with get_store() as store:
        # Get terms with optional filtering
        terms_data = store.get_glossary_terms(prefix=prefix, limit=limit, offset=offset)

        # Get total count for pagination
        total = store.get_glossary_term_count()

        # Convert domain models to response models
        terms = []
        for term_data in terms_data:
            # Parse synonyms from JSON if present
            synonyms_json = term_data.get("synonyms")
            synonyms = []
            if synonyms_json:
                try:
                    import json
                    synonyms = json.loads(synonyms_json) if isinstance(synonyms_json, str) else synonyms_json
                except Exception:
                    synonyms = []

            terms.append(
                GlossaryTerm(
                    code_term=term_data["code_term"],
                    business_meaning=term_data["business_meaning"],
                    synonyms=synonyms,
                    source_fqn=term_data.get("source_fqn"),
                    examples=[],  # Could be generated from actual code usage
                    created_at=term_data.get("created_at", ""),
                )
            )

        return GlossaryTermList(
            terms=terms,
            total=total,
            limit=limit,
            offset=offset,
        )


@router.get("/{code_term}", response_model=GlossaryTerm, tags=["glossary"])
async def get_glossary_term(code_term: str) -> GlossaryTerm:
    """Get specific glossary term with business meaning.

    Returns detailed business meaning for a specific code term,
    helping agents understand domain vocabulary.
    """
    with get_store() as store:
        term_data = store.get_glossary_term(code_term)

        if not term_data:
            raise HTTPException(
                status_code=404,
                detail=f"Glossary term '{code_term}' not found"
            )

        # Parse synonyms from JSON if present
        synonyms_json = term_data.get("synonyms")
        synonyms = []
        if synonyms_json:
            try:
                import json
                synonyms = json.loads(synonyms_json) if isinstance(synonyms_json, str) else synonyms_json
            except Exception:
                synonyms = []

        return GlossaryTerm(
            code_term=term_data["code_term"],
            business_meaning=term_data["business_meaning"],
            synonyms=synonyms,
            source_fqn=term_data.get("source_fqn"),
            examples=[],
            created_at=term_data.get("created_at", ""),
        )


@router.get("/search/{query}", response_model=GlossarySearchResponse, tags=["glossary"])
async def search_glossary(
    query: str,
    num_results: int = Query(10, ge=1, le=100, description="Number of results"),
) -> GlossarySearchResponse:
    """Search glossary terms by query.

    Performs prefix matching on code terms and contains search
    on business meanings to find relevant domain vocabulary.

    This is a lightweight search - for semantic search, use the
    main search endpoint with vector embeddings.
    """
    with get_store() as store:
        # Search by code_term prefix
        terms_data = store.get_glossary_terms(prefix=query, limit=num_results)

        # Also search by business_meaning contains
        cursor = store.conn.cursor()
        cursor.execute(
            """
            SELECT * FROM glossary
            WHERE business_meaning LIKE ?
            ORDER BY code_term
            LIMIT ?
            """,
            (f"%{query}%", num_results)
        )
        meaning_matches = [dict(row) for row in cursor.fetchall()]

        # Combine results, deduplicating by code_term
        seen_terms = set()
        results = []

        for term_data in terms_data:
            code_term = term_data["code_term"]
            if code_term not in seen_terms:
                seen_terms.add(code_term)

                # Parse synonyms
                synonyms_json = term_data.get("synonyms")
                synonyms = []
                if synonyms_json:
                    try:
                        import json
                        synonyms = json.loads(synonyms_json) if isinstance(synonyms_json, str) else synonyms_json
                    except Exception:
                        synonyms = []

                results.append(
                    GlossaryTerm(
                        code_term=term_data["code_term"],
                        business_meaning=term_data["business_meaning"],
                        synonyms=synonyms,
                        source_fqn=term_data.get("source_fqn"),
                        examples=[],
                        created_at=term_data.get("created_at", ""),
                    )
                )

        # Add meaning matches not already included
        for term_data in meaning_matches:
            code_term = term_data["code_term"]
            if code_term not in seen_terms:
                seen_terms.add(code_term)

                # Parse synonyms
                synonyms_json = term_data.get("synonyms")
                synonyms = []
                if synonyms_json:
                    try:
                        import json
                        synonyms = json.loads(synonyms_json) if isinstance(synonyms_json, str) else synonyms_json
                    except Exception:
                        synonyms = []

                results.append(
                    GlossaryTerm(
                        code_term=term_data["code_term"],
                        business_meaning=term_data["business_meaning"],
                        synonyms=synonyms,
                        source_fqn=term_data.get("source_fqn"),
                        examples=[],
                        created_at=term_data.get("created_at", ""),
                    )
                )

        return GlossarySearchResponse(
            query=query,
            results=results[:num_results],
            num_results=len(results[:num_results]),
        )
