import asyncio
import os
import sys
import time
import numpy as np

# Add project root to path
sys.path.append(os.getcwd())

from bimcalc.db.connection import get_session
from bimcalc.db.models import DocumentModel
from sqlalchemy import select


async def verify_performance():
    print("🧪 Verifying Vector Search Performance...")

    # Generate dummy embeddings
    dim = 1536
    num_docs = 100

    async with get_session() as session:
        # Cleanup
        from sqlalchemy import text

        await session.execute(
            text("DELETE FROM documents WHERE title LIKE 'PerfTest%'")
        )
        await session.commit()

        print(f"   Inserting {num_docs} documents...")
        docs = []
        for i in range(num_docs):
            embedding = np.random.rand(dim).tolist()
            docs.append(
                DocumentModel(
                    title=f"PerfTest Doc {i}",
                    content=f"Content for doc {i}",
                    embedding=embedding,
                    doc_metadata={"type": "test"},
                    tags=["perf"],
                )
            )
        session.add_all(docs)
        await session.commit()

        # Benchmark Search
        query_vec = np.random.rand(dim).tolist()

        start_time = time.time()

        # Check dialect
        bind = session.bind
        if bind.dialect.name == "sqlite":
            # SQLite fallback: Fetch all and compute in memory (slow but functional)
            print("   ⚠️  Running on SQLite: Performing in-memory vector search...")
            stmt = select(DocumentModel)
            all_docs = (await session.execute(stmt)).scalars().all()

            # Simple cosine distance
            def cosine_dist(v1, v2):
                v1 = np.array(v1)
                v2 = np.array(v2)
                return 1 - np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

            results = sorted(
                all_docs, key=lambda d: cosine_dist(d.embedding, query_vec)
            )[:5]
        else:
            # Postgres: Use pgvector operator
            stmt = (
                select(DocumentModel)
                .order_by(DocumentModel.embedding.cosine_distance(query_vec))
                .limit(5)
            )
            results = (await session.execute(stmt)).scalars().all()

        end_time = time.time()

        duration_ms = (end_time - start_time) * 1000
        print(f"✅ Search completed in {duration_ms:.2f}ms")
        print(f"   Found {len(results)} results")

        # Basic assertion (SQLite won't be super fast, but should work)
        assert len(results) == 5

        # Cleanup
        await session.execute(
            text("DELETE FROM documents WHERE title LIKE 'PerfTest%'")
        )
        await session.commit()


if __name__ == "__main__":
    asyncio.run(verify_performance())
