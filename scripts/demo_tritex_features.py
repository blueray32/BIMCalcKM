import asyncio
import sys
import os
from sqlalchemy import select

# Add project root to path
sys.path.append(os.getcwd())

from bimcalc.db.connection import get_session
from bimcalc.db.models import ItemModel, DocumentLinkModel, DocumentModel


async def demo():
    print("\n--- DEMO: Tritex24-229 Intelligent Features ---\n")

    async with get_session() as session:
        # 1. Show Linked Items
        print("1. Items with Linked Documents (Auto-Matched):")
        print("-" * 50)

        # Fetch items that have links
        stmt = (
            select(ItemModel)
            .join(DocumentLinkModel)
            .join(DocumentModel)
            # .options(selectinload(ItemModel.attributes)) # Removed: attributes is a column, not a relationship
            # .distinct() # Removed: causes error with JSON columns
            .limit(5)
        )

        result = await session.execute(stmt)
        items = result.scalars().all()

        if not items:
            print("No linked items found yet (try ingesting more documents).")

        for item in items:
            # Fetch the specific links for this item
            link_stmt = (
                select(DocumentLinkModel, DocumentModel)
                .join(DocumentModel)
                .where(DocumentLinkModel.item_id == item.id)
            )
            links = await session.execute(link_stmt)

            print(f"Item: {item.type_name} (Family: {item.family})")
            for link, doc in links:
                print(f"  -> Linked Doc: {doc.title} [{doc.doc_type}]")
                print(f"     Tags: {doc.tags}")
                print(f"     Confidence: {link.confidence}")
            print("")

        # 2. Document Search by Tag
        print("\n2. Finding Contracts (Tag Search):")
        print("-" * 50)
        stmt = select(DocumentModel).limit(100)
        result = await session.execute(stmt)
        all_docs = result.scalars().all()
        contracts = [d for d in all_docs if "#Contract" in d.tags][:5]

        for doc in contracts:
            print(f"Contract Doc: {doc.title}")
            print(f"  Source: {doc.source_file}")

        # 3. RAG / Semantic Search (Simulation)
        print("\n3. RAG / Semantic Search Capability:")
        print("-" * 50)
        print("Query: 'What is the warranty period?'")
        # In a real scenario with embeddings, we would do:
        # embedding = await get_embedding("What is the warranty period?")
        # stmt = select(DocumentModel).order_by(DocumentModel.embedding.cosine_distance(embedding)).limit(1)
        # But for this demo without guaranteed API key, we'll show the SQL capability:
        print("SQL: SELECT * FROM documents ORDER BY embedding <=> [vector] LIMIT 1")
        print("Result: (Would return the specific contract clause)")


if __name__ == "__main__":
    asyncio.run(demo())
