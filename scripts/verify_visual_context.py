import asyncio
from pathlib import Path
from bimcalc.db.connection import get_session
from bimcalc.ingestion.schedules import ingest_schedule
from bimcalc.db.models import ItemModel
from sqlalchemy import select, text


async def test_ingest():
    async with get_session() as session:
        # Clean up previous test data
        org_id = "test-org-visual"
        project_id = "test-proj-visual"

        print("Cleaning up previous test data...")
        await session.execute(text(f"DELETE FROM items WHERE org_id = '{org_id}'"))
        await session.commit()

        file_path = Path("tests/data/sample_schedule_with_id.csv")

        print(f"Ingesting {file_path}...")
        success, errors = await ingest_schedule(session, file_path, org_id, project_id)

        print(f"Success: {success}, Errors: {errors}")

        # Verify
        stmt = select(ItemModel).where(
            ItemModel.org_id == org_id, ItemModel.project_id == project_id
        )
        result = await session.execute(stmt)
        items = result.scalars().all()

        print(f"Found {len(items)} items.")
        for item in items:
            print(
                f"Item: {item.family} / {item.type_name}, Element ID: {item.element_id}"
            )
            if item.element_id not in ["345123", "345124"]:
                print("FAIL: Element ID mismatch")
            else:
                print("PASS: Element ID matches")


if __name__ == "__main__":
    asyncio.run(test_ingest())
