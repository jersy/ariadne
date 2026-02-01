"""Symbol detail endpoint."""

import logging
import os

from fastapi import APIRouter, HTTPException, Path

from ariadne_api.schemas.symbol import SymbolDetail
from ariadne_core.storage.sqlite_store import SQLiteStore

router = APIRouter()
logger = logging.getLogger(__name__)


def get_store() -> SQLiteStore:
    """Dependency to get SQLite store."""
    db_path = os.environ.get("ARIADNE_DB_PATH", "ariadne.db")
    if not os.path.exists(db_path):
        raise HTTPException(status_code=503, detail="Database not available")
    return SQLiteStore(db_path)


@router.get("/knowledge/symbol/{fqn}", response_model=SymbolDetail, tags=["symbol"])
async def get_symbol_detail(
    fqn: str = Path(..., description="Fully qualified symbol name"),
) -> SymbolDetail:
    """Get detailed information about a specific symbol.

    Returns symbol metadata, signature, location, and related information
    such as business summary and entry point details.
    """
    store = get_store()

    # Get symbol details
    symbol = store.get_symbol(fqn)
    if not symbol:
        raise HTTPException(status_code=404, detail=f"Symbol not found: {fqn}")

    # Get summary if available
    summary_data = store.get_summary(fqn)
    summary = summary_data["summary"] if summary_data else None

    # Get entry point if applicable
    cursor = store.conn.cursor()
    cursor.execute(
        "SELECT * FROM entry_points WHERE symbol_fqn = ?",
        (fqn,),
    )
    entry_point_row = cursor.fetchone()
    entry_point = None
    if entry_point_row:
        entry_point = dict(entry_point_row)

    return SymbolDetail(
        fqn=symbol["fqn"],
        kind=symbol["kind"],
        name=symbol["name"],
        file_path=symbol.get("file_path"),
        line_number=symbol.get("line_number"),
        modifiers=symbol.get("modifiers", []).split(",") if symbol.get("modifiers") else [],
        signature=symbol.get("signature"),
        parent_fqn=symbol.get("parent_fqn"),
        annotations=symbol.get("annotations", "").split(",") if symbol.get("annotations") else [],
        summary=summary,
        entry_point=entry_point,
    )
