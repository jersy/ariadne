"""Glossary API endpoints for domain vocabulary access."""

import json
import logging
import re
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

from ariadne_api.dependencies import get_store
from ariadne_api.schemas.glossary import (
    GlossarySearchResponse,
    GlossaryTerm,
    GlossaryTermList,
)

router = APIRouter(prefix="/glossary")
logger = logging.getLogger(__name__)


def escape_like_pattern(pattern: str) -> str:
    """Escape SQL LIKE special characters in search pattern.

    Args:
        pattern: User-provided search string

    Returns:
        Escaped string safe for use in LIKE clause

    Example:
        >>> escape_like_pattern("test%")
        'test\\%'
        >>> escape_like_pattern("user_data")
        'user\\_data'
    """
    # Escape backslashes first, then wildcard characters (% and _)
    return re.sub(r'([\\%_])', r'\\\1', pattern)


def parse_synonyms(synonyms_json: Any) -> list[str]:
    """Parse synonyms from JSON storage.

    Handles both string JSON and pre-parsed lists.
    Returns empty list on any error or if input is None.

    Args:
        synonyms_json: Either a JSON string or a list

    Returns:
        List of synonym strings, empty list on error
    """
    # Handle None/empty input
    if not synonyms_json:
        return []

    # If already a list, validate and return
    if isinstance(synonyms_json, list):
        return synonyms_json if all(isinstance(s, str) for s in synonyms_json) else []

    # If string, try to parse JSON
    if isinstance(synonyms_json, str):
        try:
            parsed = json.loads(synonyms_json)
            if isinstance(parsed, list):
                return parsed if all(isinstance(s, str) for s in parsed) else []
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

    # Fallback for any other type
    return []


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
            synonyms = parse_synonyms(term_data.get("synonyms"))

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
        synonyms = parse_synonyms(term_data.get("synonyms"))

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
        # Escape LIKE wildcards to prevent injection
        cursor = store.conn.cursor()
        safe_query = escape_like_pattern(query)
        cursor.execute(
            """
            SELECT * FROM glossary
            WHERE business_meaning LIKE ?
            ORDER BY code_term
            LIMIT ?
            """,
            (f"%{safe_query}%", num_results)
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
                synonyms = parse_synonyms(term_data.get("synonyms"))

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
                synonyms = parse_synonyms(term_data.get("synonyms"))

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
