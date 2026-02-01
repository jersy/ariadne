"""Schemas for glossary API endpoints."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class GlossaryTerm(BaseModel):
    """A domain glossary term mapping code to business meaning."""

    code_term: str = Field(description="Code term (e.g., 'Sku', 'OrderId')")
    business_meaning: str = Field(description="Business meaning of the term")
    synonyms: list[str] = Field(
        default_factory=list,
        description="Alternative terms or synonyms"
    )
    source_fqn: Optional[str] = Field(
        default=None,
        description="Source symbol FQN where this term was extracted"
    )
    examples: list[str] = Field(
        default_factory=list,
        description="Usage examples (can be generated from actual code)"
    )
    created_at: str = Field(description="When this term was added to the glossary")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "code_term": "Sku",
                "business_meaning": "Stock Keeping Unit - 唯一标识一个可售卖的商品规格",
                "synonyms": ["规格", "商品SKU"],
                "source_fqn": "com.example.product.Sku",
                "examples": [
                    "iPhone 15 Pro 256GB Black",
                    "Nike Air Max 90 Size 42"
                ],
                "created_at": "2026-02-02T12:00:00",
            }
        }
    )


class GlossaryTermList(BaseModel):
    """List of glossary terms with pagination."""

    terms: list[GlossaryTerm] = Field(description="List of glossary terms")
    total: int = Field(description="Total number of terms")
    limit: int = Field(description="Maximum results returned")
    offset: int = Field(description="Pagination offset")


class GlossarySearchResponse(BaseModel):
    """Response from glossary semantic search."""

    query: str = Field(description="Original search query")
    results: list[GlossaryTerm] = Field(description="Matching glossary terms")
    num_results: int = Field(description="Number of results found")
