"""Compliance Engine for BIMCalc.

Evaluates project items against organization-specific compliance rules.
"""

from __future__ import annotations

from typing import List, Optional
from uuid import uuid4

from bimcalc.db.models import ItemModel, PriceItemModel
from bimcalc.db.models_intelligence import ComplianceRuleModel, ComplianceResultModel


class ComplianceEngine:
    """Evaluates compliance rules for project items."""

    def evaluate_item(
        self,
        item: ItemModel,
        price_item: Optional[PriceItemModel],
        rules: List[ComplianceRuleModel],
    ) -> List[ComplianceResultModel]:
        """Evaluate an item against a list of rules.

        Args:
            item: The item to check
            price_item: The matched price item (if any)
            rules: List of active compliance rules

        Returns:
            List of ComplianceResultModel (one for each rule)
        """
        results = []

        for rule in rules:
            passed = True
            message = "Passed"

            if rule.rule_type == "classification_required":
                if not item.classification_code:
                    passed = False
                    message = "Item is missing classification code"

            elif rule.rule_type == "vendor_whitelist":
                allowed_vendors = rule.configuration.get("vendors", [])
                if price_item:
                    # Check source_name or vendor_name (assuming source_name is used for now)
                    vendor = price_item.source_name
                    if vendor not in allowed_vendors:
                        passed = False
                        message = f"Vendor '{vendor}' is not in the whitelist"
                else:
                    # If no price item, we can't check vendor, so maybe skip or fail?
                    # Let's say it passes if no vendor is selected yet, or maybe N/A
                    # For strict compliance, let's say it passes this check until a vendor is selected
                    pass

            elif rule.rule_type == "currency_check":
                allowed_currencies = rule.configuration.get("currencies", ["EUR"])
                if price_item:
                    if price_item.currency not in allowed_currencies:
                        passed = False
                        message = f"Currency '{price_item.currency}' is not allowed"

            results.append(
                ComplianceResultModel(
                    id=uuid4(),
                    org_id=item.org_id,
                    project_id=item.project_id,
                    item_id=item.id,
                    rule_id=rule.id,
                    passed=passed,
                    message=message,
                )
            )

        return results
