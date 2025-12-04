"""Risk Scoring Engine for BIMCalc items.

Calculates multi-dimensional risk scores to identify potential issues
in cost estimation and data quality.
"""

from __future__ import annotations

from uuid import uuid4

from bimcalc.db.models import ItemModel, MatchResultModel, PriceItemModel
from bimcalc.db.models_intelligence import RiskScoreModel


class RiskEngine:
    """Calculates risk scores for project items."""

    def calculate_item_risk(
        self,
        item: ItemModel,
        match_result: MatchResultModel | None,
        price_item: PriceItemModel | None = None,
    ) -> RiskScoreModel:
        """Compute comprehensive risk score for an item.

        Args:
            item: The project item to analyze
            match_result: The active match result (if any)
            price_item: The matched price item (if any)

        Returns:
            RiskScoreModel with calculated scores
        """
        risk_factors = {}

        # 1. Confidence Risk (Weight: 40%)
        confidence_risk = 100.0
        if match_result:
            # Invert confidence: 100% confidence = 0% risk
            confidence_risk = max(0.0, 100.0 - float(match_result.confidence_score))

            # Penalize manual review if not explicitly approved
            if match_result.decision == "manual-review":
                confidence_risk = max(confidence_risk, 50.0)
                risk_factors["manual_review_pending"] = "Item requires manual review"
        else:
            risk_factors["no_match"] = "Item has no match"

        # 2. Price Risk (Weight: 30%)
        price_risk = 0.0
        if price_item:
            # Check for high unit price (outlier detection placeholder)
            if price_item.unit_price > 1000:
                price_risk += 20.0
                risk_factors["high_value_item"] = "Unit price > 1000"

            # Check for currency mismatch risk
            if price_item.currency != "EUR":  # Assuming base currency
                price_risk += 10.0
                risk_factors["currency_mismatch"] = f"Currency is {price_item.currency}"
        else:
            price_risk = 100.0  # No price = max risk
            risk_factors["missing_price"] = "No price item linked"

        # 3. Data Quality Risk (Weight: 30%)
        data_quality_risk = 0.0

        if not item.classification_code:
            data_quality_risk += 50.0
            risk_factors["missing_classification"] = "No classification code"

        if not item.quantity or item.quantity <= 0:
            data_quality_risk += 50.0
            risk_factors["invalid_quantity"] = "Quantity is missing or zero"

        # Calculate Weighted Total
        total_score = (
            (confidence_risk * 0.40) + (price_risk * 0.30) + (data_quality_risk * 0.30)
        )

        return RiskScoreModel(
            id=uuid4(),
            org_id=item.org_id,
            project_id=item.project_id,
            item_id=item.id,
            total_risk_score=min(100.0, total_score),
            confidence_risk=confidence_risk,
            price_risk=price_risk,
            data_quality_risk=data_quality_risk,
            risk_factors=risk_factors,
        )
