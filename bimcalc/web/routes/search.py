from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select, text
from typing import List

from bimcalc.db.connection import get_session
from bimcalc.web.auth import require_auth
from bimcalc.web.dependencies import get_templates
from bimcalc.core.embeddings import generate_embedding

router = APIRouter(prefix="/search", tags=["search"])

@router.get("/", response_class=HTMLResponse)
async def search(
    request: Request,
    q: str = Query(None),
    user=Depends(require_auth),
    templates=Depends(get_templates),
):
    if not q:
        return templates.TemplateResponse(
            "search_results.html",
            {"request": request, "query": None, "results": {}}
        )

    embedding = await generate_embedding(q)
    if not embedding:
        return templates.TemplateResponse(
            "search_results.html",
            {"request": request, "query": q, "results": {}, "error": "Failed to generate embedding"}
        )

    embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

    async with get_session() as session:
        # Search Items
        items_query = text("""
            SELECT id, family, type_name, classification_code, 
                   1 - (embedding <=> CAST(:embedding AS vector)) as similarity
            FROM items
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:embedding AS vector)
            LIMIT 5
        """)
        items_result = await session.execute(items_query, {"embedding": embedding_str})
        items = items_result.fetchall()

        # Search Price Items
        prices_query = text("""
            SELECT id, description, vendor_code, sku, unit_price, currency,
                   1 - (embedding <=> CAST(:embedding AS vector)) as similarity
            FROM price_items
            WHERE embedding IS NOT NULL AND is_current = true
            ORDER BY embedding <=> CAST(:embedding AS vector)
            LIMIT 5
        """)
        prices_result = await session.execute(prices_query, {"embedding": embedding_str})
        prices = prices_result.fetchall()

        # Search Documents
        docs_query = text("""
            SELECT id, title, doc_type, 
                   1 - (embedding <=> CAST(:embedding AS vector)) as similarity
            FROM documents
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:embedding AS vector)
            LIMIT 5
        """)
        docs_result = await session.execute(docs_query, {"embedding": embedding_str})
        docs = docs_result.fetchall()

    return templates.TemplateResponse(
        "search_results.html",
        {
            "request": request,
            "query": q,
            "results": {
                "items": items,
                "prices": prices,
                "documents": docs
            },
            "user": user
        }
    )
