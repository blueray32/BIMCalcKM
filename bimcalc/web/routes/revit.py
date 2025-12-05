from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from bimcalc.core.embeddings import generate_embedding
from bimcalc.db.connection import get_db
from bimcalc.matching.smart_matcher import find_matches_by_embedding
from bimcalc.web.models import RevitItemInput, RevitMatchResponse

router = APIRouter(prefix="/api/revit", tags=["Revit Integration"])


@router.post("/match", response_model=List[RevitMatchResponse])
async def match_revit_items(
    items: List[RevitItemInput],
    org_id: str = "default",  # In production, this would come from auth/API key
    project_id: str = "default",
    db: AsyncSession = Depends(get_db),
    # user=Depends(get_current_user), # TODO: Enable auth for plugin
) -> List[RevitMatchResponse]:
    """Match a batch of Revit elements to price items.

    Receives a list of Revit elements (Family, Type, Parameters),
    runs them through the Smart Matcher, and returns the best match
    for each item along with confidence scores.
    """
    results = []

    for item_input in items:
        # Construct text representation for embedding
        # Similar to how ItemModel generates its embedding text
        text_parts = [
            f"Family: {item_input.family}",
            f"Type: {item_input.type_name}",
            f"Category: {item_input.category or ''}",
        ]
        
        # Add parameters to text
        for key, value in item_input.parameters.items():
            if value:
                text_parts.append(f"{key}: {value}")
                
        text_representation = " ".join(text_parts)
        
        # Generate embedding
        embedding = await generate_embedding(text_representation)
        
        matches = []
        if embedding:
            # Run matching
            matches = await find_matches_by_embedding(db, embedding, limit=1)

        response = RevitMatchResponse(
            element_id=item_input.element_id,
            match_source="none",
            confidence_score=0.0
        )

        if matches:
            best_match = matches[0]
            response.price_item_id = UUID(best_match["id"])
            response.confidence_score = best_match["similarity"]
            response.match_source = "fuzzy"
            
            # Include price data for the plugin to display
            response.price_data = {
                "sku": best_match["sku"],
                "description": best_match["description"],
                "unit_price": float(best_match["unit_price"]) if best_match["unit_price"] else 0.0,
                "currency": best_match["currency"],
                "vendor": best_match["vendor_id"]
            }

        results.append(response)

    return results
