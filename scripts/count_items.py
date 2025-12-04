import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from bimcalc.db.connection import get_session
from bimcalc.db.models import ItemModel
from sqlalchemy import select, func


async def count():
    async with get_session() as session:
        count = await session.scalar(
            select(func.count()).where(ItemModel.project_id == "tritex24-229")
        )
        print(f"Total items for project tritex24-229: {count}")


if __name__ == "__main__":
    asyncio.run(count())
