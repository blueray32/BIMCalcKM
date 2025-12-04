"""Verification script for Risk Scoring Engine."""

import asyncio
from uuid import uuid4
from decimal import Decimal

from bimcalc.intelligence.risk_engine import RiskEngine
from bimcalc.db.models import ItemModel, MatchResultModel, PriceItemModel


async def verify_risk_engine():
    print("🧪 Verifying Risk Scoring Engine...")

    engine = RiskEngine()
    org_id = "test-org-risk"
    project_id = "test-proj-risk"

    # Scenario 1: Perfect Match (Low Risk)
    print("\n   Scenario 1: Perfect Match")
    item1 = ItemModel(
        id=uuid4(),
        org_id=org_id,
        project_id=project_id,
        classification_code="123",
        quantity=Decimal("10.0"),
        family="Test",
        type_name="Test",
    )
    price1 = PriceItemModel(
        id=uuid4(),
        org_id=org_id,
        item_code="P1",
        region="EU",
        unit_price=Decimal("100.00"),
        currency="EUR",
        source_name="Vendor A",
        description="Desc",
        unit="ea",
        sku="SKU1",
        classification_code="123",
    )
    match1 = MatchResultModel(
        id=uuid4(),
        item_id=item1.id,
        price_item_id=price1.id,
        confidence_score=100.0,
        decision="auto-accepted",
        source="fuzzy",
        reason="perfect",
        created_by="system",
    )

    score1 = engine.calculate_item_risk(item1, match1, price1)
    print(f"   Score: {score1.total_risk_score:.2f} (Expected ~0)")
    if score1.total_risk_score < 5.0:
        print("   ✅ Low risk verified")
    else:
        print(f"   ❌ Unexpected high risk: {score1.total_risk_score}")

    # Scenario 2: High Risk (Low confidence, missing data)
    print("\n   Scenario 2: High Risk")
    item2 = ItemModel(
        id=uuid4(),
        org_id=org_id,
        project_id=project_id,
        classification_code=None,
        quantity=Decimal("0.0"),  # Missing class & quantity
        family="Test",
        type_name="Test",
    )
    match2 = MatchResultModel(
        id=uuid4(),
        item_id=item2.id,
        price_item_id=None,
        confidence_score=50.0,
        decision="manual-review",  # Low confidence & manual review
        source="fuzzy",
        reason="weak",
        created_by="system",
    )

    score2 = engine.calculate_item_risk(item2, match2, None)  # No price item
    print(f"   Score: {score2.total_risk_score:.2f} (Expected >= 80)")
    print(f"   Factors: {score2.risk_factors}")

    if score2.total_risk_score >= 80.0:
        print("   ✅ High risk verified")
    else:
        print(f"   ❌ Unexpected low risk: {score2.total_risk_score}")


if __name__ == "__main__":
    asyncio.run(verify_risk_engine())
