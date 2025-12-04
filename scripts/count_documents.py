import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from bimcalc.db.connection import get_session
from bimcalc.db.models import DocumentModel
from sqlalchemy import select, func


async def count():
    async with get_session() as session:
        count = await session.scalar(select(func.count(DocumentModel.id)))
        print(f"Total documents: {count}")


if __name__ == "__main__":
    asyncio.run(count())
