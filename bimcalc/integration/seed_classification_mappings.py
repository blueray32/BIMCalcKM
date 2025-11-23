"""Seed classification mappings from CSV."""

from __future__ import annotations

import asyncio
import csv
import uuid
from pathlib import Path

from bimcalc.db.connection import get_session
from bimcalc.db.models import ClassificationMappingModel


async def seed_mappings(org_id: str, csv_path: str) -> None:
    """Load classification mappings from CSV into the database."""
    csv_file = Path(csv_path)
    if not csv_file.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_file}")

    async with get_session() as session:
        with csv_file.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                mapping = ClassificationMappingModel(
                    id=str(uuid.uuid4()),
                    org_id=org_id,
                    source_scheme=row["source_scheme"],
                    source_code=row["source_code"],
                    target_scheme=row["target_scheme"],
                    target_code=row["target_code"],
                    confidence=float(row.get("confidence", 1.0)),
                    mapping_source=row.get("mapping_source"),
                    created_by="seed_script",
                )
                session.add(mapping)

        await session.commit()
        print(f"Seeded classification mappings for {org_id} from {csv_file}")


if __name__ == "__main__":
    asyncio.run(
        seed_mappings(
            org_id="acme-construction",
            csv_path="data/classification_mappings.csv",
        )
    )
