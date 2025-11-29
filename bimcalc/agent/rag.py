"""RAG Service for BIMCalc Agent.

Handles document ingestion (embedding generation) and semantic search using pgvector.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from bimcalc.config import get_config
from bimcalc.db.connection import get_session
from bimcalc.db.models import DocumentModel

# Optional dependency for OpenAI
try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None


class RAGService:
    """Service for RAG operations (ingest, search)."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.config = get_config()
        self.client = None
        
        if self.config.llm.provider == "openai" and self.config.llm.api_key:
            if AsyncOpenAI:
                self.client = AsyncOpenAI(api_key=self.config.llm.api_key)
            else:
                # Fallback or warning if openai package missing but config present
                pass

    async def get_embedding(self, text_content: str) -> list[float]:
        """Generate embedding for text using configured model."""
        if not self.client:
            # Mock embedding for testing/dev if no API key
            # 1536 dimensions for text-embedding-3-large compatibility
            return [0.0] * 1536

        response = await self.client.embeddings.create(
            input=text_content,
            model=self.config.llm.embeddings_model,
            dimensions=1536  # Force 1536 dimensions to match DB schema
        )
        return response.data[0].embedding

    async def ingest_document(
        self,
        title: str,
        content: str,
        doc_type: str = "general",
        metadata: dict[str, Any] | None = None,
        source_file: str | None = None,
    ) -> DocumentModel:
        """Ingest a document into the knowledge base."""
        embedding = await self.get_embedding(content)

        doc = DocumentModel(
            title=title,
            content=content,
            embedding=embedding,
            doc_type=doc_type,
            metadata=metadata or {},
            source_file=source_file,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.session.add(doc)
        await self.session.commit()
        return doc

    async def search(self, query: str, limit: int = 5) -> list[DocumentModel]:
        """Perform semantic search for documents."""
        query_embedding = await self.get_embedding(query)
        
        # Check dialect
        dialect = self.session.bind.dialect.name if self.session.bind else "sqlite"
        
        if dialect == "postgresql":
            # pgvector cosine distance operator: <=>
            stmt = select(DocumentModel).order_by(
                DocumentModel.embedding.cosine_distance(query_embedding)
            ).limit(limit)
            result = await self.session.execute(stmt)
            return result.scalars().all()
        else:
            # SQLite fallback: Fetch all and sort in Python
            # Note: This is inefficient for large datasets but fine for MVP/testing
            stmt = select(DocumentModel)
            result = await self.session.execute(stmt)
            docs = result.scalars().all()
            
            if not docs:
                return []

            def cosine_similarity(v1, v2):
                if v1 is None or v2 is None or len(v1) == 0 or len(v2) == 0: return 0.0
                dot_product = sum(a * b for a, b in zip(v1, v2))
                norm_a = sum(a * a for a in v1) ** 0.5
                norm_b = sum(b * b for b in v2) ** 0.5
                return dot_product / (norm_a * norm_b) if norm_a and norm_b else 0.0

            # Calculate similarity and sort
            scored_docs = []
            for doc in docs:
                # Handle string embedding from SQLite if stored as JSON/string
                embedding = doc.embedding
                if isinstance(embedding, str):
                    import json
                    try:
                        embedding = json.loads(embedding)
                    except:
                        embedding = []
                
                score = cosine_similarity(query_embedding, embedding)
                scored_docs.append((score, doc))
            
            # Sort by score descending
            scored_docs.sort(key=lambda x: x[0], reverse=True)
            return [doc for _, doc in scored_docs[:limit]]

    async def chat(self, query: str) -> str:
        """Simple RAG chat: Search + Generate (Mock generation for MVP)."""
        docs = await self.search(query, limit=3)
        
        if not docs:
            return "I couldn't find any relevant information in my knowledge base."

        # For MVP, we just return the search results as a summary
        # In a full implementation, this would call the LLM with a prompt
        response = "Here's what I found:\n\n"
        for doc in docs:
            response += f"**{doc.title}**\n{doc.content[:200]}...\n\n"
            
        return response
