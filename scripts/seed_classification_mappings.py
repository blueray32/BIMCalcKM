"""Seed initial classification mapping for Tritex project."""

import asyncio
import sys
import os

sys.path.append(os.getcwd())

from bimcalc.db.connection import get_session
from bimcalc.db.models import ProjectClassificationMappingModel


async def main():
    """Add initial mapping: 61 -> 2601 for tritex24-229 project."""
    async with get_session() as session:
        # Check if mapping already exists
        from sqlalchemy import select

        existing = await session.execute(
            select(ProjectClassificationMappingModel).where(
                ProjectClassificationMappingModel.org_id == "demo-org",
                ProjectClassificationMappingModel.project_id == "tritex24-229",
                ProjectClassificationMappingModel.local_code == "61",
            )
        )

        if existing.scalar_one_or_none():
            print("Mapping already exists!")
            return

        mapping = ProjectClassificationMappingModel(
            org_id="demo-org",
            project_id="tritex24-229",
            local_code="61",
            standard_code="2601",
            description="Electrical Distribution - Tritex project-specific code",
            created_by="seed-script",
        )

        session.add(mapping)
        await session.commit()

        print("✓ Created mapping: 61 → 2601 (Electrical Distribution)")


if __name__ == "__main__":
    asyncio.run(main())
