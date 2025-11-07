"""Backfill canonical keys for existing items."""
import asyncio
from sqlalchemy import select, update
from bimcalc.db.connection import get_session
from bimcalc.db.models import ItemModel
from bimcalc.models import Item
from bimcalc.canonical.key_generator import canonical_key
from bimcalc.classification.trust_hierarchy import classify_item

async def backfill_canonical_keys():
    """Update all items with their canonical keys."""
    async with get_session() as session:
        # Get all items
        result = await session.execute(select(ItemModel))
        items = result.scalars().all()

        updated = 0
        for item_model in items:
            # Convert to Pydantic Item
            item = Item(
                id=str(item_model.id),
                org_id=item_model.org_id,
                project_id=item_model.project_id,
                family=item_model.family,
                type_name=item_model.type_name,
                category=item_model.category,
                system_type=item_model.system_type,
                quantity=float(item_model.quantity) if item_model.quantity else None,
                unit=item_model.unit,
                width_mm=item_model.width_mm,
                height_mm=item_model.height_mm,
                dn_mm=item_model.dn_mm,
                angle_deg=item_model.angle_deg,
                material=item_model.material,
            )

            # Classify item
            item.classification_code = classify_item(item)

            # Calculate canonical key
            key = canonical_key(item)

            # Update model
            item_model.canonical_key = key
            item_model.classification_code = item.classification_code
            updated += 1

        await session.commit()
        print(f"✓ Updated {updated} items with canonical keys")

if __name__ == "__main__":
    asyncio.run(backfill_canonical_keys())
