"""Compliance checking engine for BIMCalc.

Handles:
1. Extracting rules from specification documents (using LLM).
2. Checking items against defined compliance rules.
"""

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bimcalc.db.models_intelligence import ComplianceResultModel, ComplianceRuleModel
from bimcalc.db.models import ItemModel

logger = logging.getLogger(__name__)


async def extract_rules_from_text(text: str) -> list[dict]:
    """Extract compliance rules from text using LLM (Mocked).

    Args:
        text: Specification text (e.g. from PDF).

    Returns:
        List of rule dictionaries:
        [
            {
                "name": "Fire Rating Requirement",
                "description": "All doors must have FD30 rating.",
                "rule_logic": {
                    "field": "fire_rating",
                    "op": ">=",
                    "val": 30
                }
            }
        ]
    """
    # TODO: Replace with actual LLM call (OpenAI/Anthropic)
    # For MVP, we return a hardcoded rule if keywords are found

    rules = []

    if "fire" in text.lower() and "door" in text.lower():
        rules.append(
            {
                "name": "Fire Door Rating",
                "description": "Doors must have at least 30 minute fire rating.",
                "rule_logic": {
                    "field": "fire_rating",
                    "op": ">=",
                    "val": 30,
                    "target_category": "Doors",  # Optional filter
                },
            }
        )

    if "copper" in text.lower() and "pipe" in text.lower():
        rules.append(
            {
                "name": "Copper Piping",
                "description": "All pipes must be made of Copper.",
                "rule_logic": {
                    "field": "material",
                    "op": "contains",
                    "val": "Copper",
                    "target_category": "Pipes",
                },
            }
        )

    return rules


async def run_compliance_check(
    session: AsyncSession,
    org_id: str,
    project_id: str,
    item_ids: list[UUID] | None = None,
) -> dict:
    """Run compliance checks for items in a project.

    Args:
        session: DB session.
        org_id: Organization ID.
        project_id: Project ID.
        item_ids: Optional list of specific items to check. If None, checks all.

    Returns:
        Summary dict: {"passed": int, "failed": int, "warnings": int}
    """
    # 1. Fetch active rules
    stmt = select(ComplianceRuleModel).where(
        ComplianceRuleModel.org_id == org_id,
        ComplianceRuleModel.project_id == project_id,
    )
    rules = (await session.execute(stmt)).scalars().all()

    if not rules:
        logger.info("No compliance rules found for project.")
        return {"passed": 0, "failed": 0, "warnings": 0}

    # 2. Fetch items
    query = select(ItemModel).where(
        ItemModel.org_id == org_id, ItemModel.project_id == project_id
    )
    if item_ids:
        query = query.where(ItemModel.id.in_(item_ids))

    items = (await session.execute(query)).scalars().all()

    stats = {"passed": 0, "failed": 0, "warnings": 0}

    # 3. Check each item against each rule
    for item in items:
        for rule in rules:
            result_status, message = _evaluate_rule(item, rule.rule_logic)

            # Save result
            result = ComplianceResultModel(
                item_id=item.id, rule_id=rule.id, status=result_status, message=message
            )
            session.add(result)

            if result_status == "pass":
                stats["passed"] += 1
            elif result_status == "fail":
                stats["failed"] += 1
            else:
                stats["warnings"] += 1

    await session.commit()
    return stats


def _evaluate_rule(item: ItemModel, logic: dict) -> tuple[str, str]:
    """Evaluate a single rule against an item.

    Returns:
        (status, message) where status is 'pass', 'fail', 'warning'
    """
    # 1. Check applicability (Target Category)
    target_category = logic.get("target_category")
    if target_category:
        # Simple string match for now
        item_cat = (item.category or "").lower()
        item_family = (item.family or "").lower()
        if (
            target_category.lower() not in item_cat
            and target_category.lower() not in item_family
        ):
            return "pass", "Rule not applicable to this item type."

    # 2. Get field value
    field = logic.get("field")
    if not field:
        return "warning", "Invalid rule: missing field definition."

    # Try direct attribute first, then attributes dict
    val = getattr(item, field, None)
    if val is None:
        val = item.attributes.get(field)

    if val is None:
        return "warning", f"Item missing required field: {field}"

    # 3. Compare
    op = logic.get("op")
    target_val = logic.get("val")

    try:
        if op == "==":
            passed = str(val).lower() == str(target_val).lower()
        elif op == "!=":
            passed = str(val).lower() != str(target_val).lower()
        elif op == ">":
            passed = float(val) > float(target_val)
        elif op == "<":
            passed = float(val) < float(target_val)
        elif op == ">=":
            passed = float(val) >= float(target_val)
        elif op == "<=":
            passed = float(val) <= float(target_val)
        elif op == "contains":
            passed = str(target_val).lower() in str(val).lower()
        else:
            return "warning", f"Unknown operator: {op}"

        if passed:
            return "pass", "Compliant"
        else:
            return "fail", f"Value '{val}' failed check {op} '{target_val}'"

    except (ValueError, TypeError):
        return "warning", f"Type mismatch comparing {val} and {target_val}"
