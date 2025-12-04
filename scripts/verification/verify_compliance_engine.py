"""Verification script for Compliance Engine."""

import asyncio
from uuid import uuid4
from decimal import Decimal

from bimcalc.intelligence.compliance_engine import ComplianceEngine
from bimcalc.db.models import ItemModel, PriceItemModel
from bimcalc.db.models_intelligence import ComplianceRuleModel


async def verify_compliance():
    print("🧪 Verifying Compliance Engine...")

    engine = ComplianceEngine()
    org_id = "test-org-comp"
    project_id = "test-proj-comp"

    # 1. Define Rules
    rule_class = ComplianceRuleModel(
        id=uuid4(),
        org_id=org_id,
        name="Class Required",
        description="Must have class",
        rule_type="classification_required",
        severity="high",
        is_active=True,
    )

    rule_vendor = ComplianceRuleModel(
        id=uuid4(),
        org_id=org_id,
        name="Vendor Whitelist",
        description="Approved vendors only",
        rule_type="vendor_whitelist",
        severity="critical",
        is_active=True,
        configuration={"vendors": ["Approved Vendor A", "Approved Vendor B"]},
    )

    rules = [rule_class, rule_vendor]

    # 2. Test Case 1: Non-Compliant Item
    print("\n   Test Case 1: Non-Compliant Item")
    item_bad = ItemModel(
        id=uuid4(),
        org_id=org_id,
        project_id=project_id,
        classification_code=None,  # Missing class
        family="Bad Item",
        type_name="Type X",
    )
    price_bad = PriceItemModel(
        id=uuid4(),
        org_id=org_id,
        item_code="P1",
        region="EU",
        unit_price=Decimal("10.0"),
        currency="EUR",
        source_name="Unknown Vendor",  # Not in whitelist
        description="Desc",
        unit="ea",
        sku="SKU1",
        classification_code="123",
        source_currency="EUR",
    )

    results_bad = engine.evaluate_item(item_bad, price_bad, rules)

    for res in results_bad:
        status = "✅ Passed" if res.passed else "❌ Failed"
        print(f"   Rule {res.rule_id}: {status} - {res.message}")

    failed_count = sum(1 for r in results_bad if not r.passed)
    if failed_count == 2:
        print("   ✅ Correctly identified 2 failures")
    else:
        print(f"   ❌ Expected 2 failures, got {failed_count}")

    # 3. Test Case 2: Compliant Item
    print("\n   Test Case 2: Compliant Item")
    item_good = ItemModel(
        id=uuid4(),
        org_id=org_id,
        project_id=project_id,
        classification_code="123",  # Has class
        family="Good Item",
        type_name="Type Y",
    )
    price_good = PriceItemModel(
        id=uuid4(),
        org_id=org_id,
        item_code="P2",
        region="EU",
        unit_price=Decimal("10.0"),
        currency="EUR",
        source_name="Approved Vendor A",  # In whitelist
        description="Desc",
        unit="ea",
        sku="SKU2",
        classification_code="123",
        source_currency="EUR",
    )

    results_good = engine.evaluate_item(item_good, price_good, rules)

    for res in results_good:
        status = "✅ Passed" if res.passed else "❌ Failed"
        print(f"   Rule {res.rule_id}: {status} - {res.message}")

    failed_count_good = sum(1 for r in results_good if not r.passed)
    if failed_count_good == 0:
        print("   ✅ Correctly identified 0 failures")
    else:
        print(f"   ❌ Expected 0 failures, got {failed_count_good}")


if __name__ == "__main__":
    asyncio.run(verify_compliance())
