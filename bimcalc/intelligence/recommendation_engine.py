"""Recommendation Engine for BIMCalc.

Generates actionable insights and recommendations to improve data quality
and reduce costs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
from uuid import UUID

from bimcalc.db.models import ItemModel, MatchResultModel, PriceItemModel


@dataclass
class Recommendation:
    """Actionable recommendation for a user."""

    type: str  # "better_match", "data_quality", "cost_saving"
    severity: str  # "high", "medium", "low"
    message: str
    action_label: str
    action_url: str
    item_id: UUID
    potential_saving: Optional[float] = None


class RecommendationEngine:
    """Analyzes project data to generate recommendations."""

    def generate_recommendations(
        self,
        items: List[ItemModel],
        matches: dict[UUID, MatchResultModel],
        price_items: dict[UUID, PriceItemModel],
    ) -> List[Recommendation]:
        """Generate a list of recommendations for the given items.

        Args:
            items: List of project items
            matches: Map of item_id -> MatchResultModel
            price_items: Map of price_item_id -> PriceItemModel

        Returns:
            List of Recommendation objects
        """
        recommendations = []

        for item in items:
            match = matches.get(item.id)
            price_item = None
            if match and match.price_item_id:
                price_item = price_items.get(match.price_item_id)

            # 1. Data Quality: Missing Classification
            if not item.classification_code:
                recommendations.append(
                    Recommendation(
                        type="data_quality",
                        severity="medium",
                        message=f"Item '{item.family}' is missing classification code.",
                        action_label="Classify",
                        action_url=f"/items/{item.id}",
                        item_id=item.id,
                    )
                )

            # 2. Data Quality: Missing Quantity
            if not item.quantity or item.quantity <= 0:
                recommendations.append(
                    Recommendation(
                        type="data_quality",
                        severity="high",
                        message=f"Item '{item.family}' has invalid quantity.",
                        action_label="Update Quantity",
                        action_url=f"/items/{item.id}",
                        item_id=item.id,
                    )
                )

            # 3. Better Match: Low confidence match
            if match and match.confidence_score < 70.0:
                recommendations.append(
                    Recommendation(
                        type="better_match",
                        severity="medium",
                        message=f"Low confidence match ({match.confidence_score:.0f}%) for '{item.family}'.",
                        action_label="Review Match",
                        action_url=f"/items/{item.id}",
                        item_id=item.id,
                    )
                )

            # 4. Cost Saving: High unit price (Simulated logic)
            # In a real system, we would query for cheaper alternatives here.
            if price_item and price_item.unit_price > 500.0:
                from decimal import Decimal

                recommendations.append(
                    Recommendation(
                        type="cost_saving",
                        severity="low",
                        message=f"High unit cost (€{price_item.unit_price:.2f}) for '{item.family}'. Check for alternatives.",
                        action_label="Find Alternative",
                        action_url=f"/items/{item.id}",
                        item_id=item.id,
                        potential_saving=float(
                            price_item.unit_price * Decimal("0.10")
                        ),  # Assume 10% saving possible
                    )
                )

        # Sort by severity (High > Medium > Low)
        severity_order = {"high": 0, "medium": 1, "low": 2}
        recommendations.sort(key=lambda r: severity_order.get(r.severity, 3))

        return recommendations
