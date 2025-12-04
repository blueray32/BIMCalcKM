"""AI-powered document linking using LLM to extract Item IDs from content."""

import asyncio
import os
import sys
from datetime import datetime

from sqlalchemy import select

# Add project root to path
sys.path.append(os.getcwd())

from bimcalc.db.connection import get_session
from bimcalc.db.models import DocumentLinkModel, DocumentModel, ItemModel

# OpenAI client setup
try:
    import openai

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    if OPENAI_API_KEY:
        openai.api_key = OPENAI_API_KEY
        AI_ENABLED = True
    else:
        print("WARNING: OPENAI_API_KEY not set. AI linking disabled.")
        AI_ENABLED = False
except ImportError:
    print("WARNING: openai package not installed. AI linking disabled.")
    AI_ENABLED = False


async def extract_item_ids_from_text(
    text: str, model: str = "gpt-4o-mini"
) -> list[str]:
    """Use OpenAI to extract Item IDs from document text.

    Args:
        text: Document content
        model: OpenAI model to use

    Returns:
        List of extracted Item IDs (e.g., ["DB-100", "SWB3"])
    """
    if not AI_ENABLED:
        return []

    # Truncate text to avoid token limits (use first 4000 chars)
    text_sample = text[:4000]

    prompt = f"""Extract all electrical equipment Item IDs mentioned in this document.
    
Item IDs typically follow these patterns:
- Distribution Boards: DB-XX (e.g., DB-100, DB-02, DB-08)
- Switchboards: SWB-X or SWBD-X (e.g., SWB3, SWBD-6)
- Panels: Various formats with numbers

Document text:
{text_sample}

Return ONLY a JSON array of Item IDs found, or an empty array if none.
Example: ["DB-100", "DB-02", "SWB3"]
"""

    try:
        response = await asyncio.to_thread(
            openai.chat.completions.create,
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at extracting equipment IDs from technical documents.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            max_tokens=200,
        )

        content = response.choices[0].message.content.strip()

        # Strip markdown code blocks if present
        if content.startswith("```"):
            # Remove ```json or ``` prefix
            content = content.split("\n", 1)[1] if "\n" in content else content[3:]
            # Remove closing ```
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

        # Parse JSON response
        import json

        try:
            item_ids = json.loads(content)
        except json.JSONDecodeError:
            # Try to extract array from response
            import re

            array_match = re.search(r"\[.*\]", content, re.DOTALL)
            if array_match:
                item_ids = json.loads(array_match.group(0))
            else:
                print(f"Warning: Could not parse response: {content[:100]}")
                return []

        if not isinstance(item_ids, list):
            print(f"Warning: Unexpected response format: {content}")
            return []

        return item_ids

    except Exception as e:
        print(f"Error extracting IDs: {e}")
        return []


async def link_document_to_items(
    session,
    document: DocumentModel,
    item_ids: list[str],
    model_used: str,
):
    """Create DocumentLink entries for extracted Item IDs.

    Args:
        session: Database session
        document: Document to link
        item_ids: List of Item IDs to link to
        model_used: LLM model used for extraction
    """
    links_created = 0

    for item_id in item_ids:
        # Find matching item by type_name (fuzzy match)
        stmt = select(ItemModel).where(ItemModel.type_name.ilike(f"%{item_id}%"))
        result = await session.execute(stmt)
        items = result.scalars().all()

        if not items:
            print(f"  No item found for ID: {item_id}")
            continue

        if len(items) > 1:
            print(f"  Multiple items found for {item_id}, using first match")

        item = items[0]

        # Check if link already exists
        existing = await session.execute(
            select(DocumentLinkModel).where(
                DocumentLinkModel.item_id == item.id,
                DocumentLinkModel.document_id == document.id,
            )
        )
        if existing.scalar_one_or_none():
            print(f"  Link already exists: {item.type_name}")
            continue

        # Create link
        link = DocumentLinkModel(
            item_id=item.id,
            document_id=document.id,
            link_type="ai_extracted",
            confidence=0.8,
            link_metadata={
                "extraction_method": "ai",
                "extraction_timestamp": datetime.utcnow().isoformat(),
                "llm_model": model_used,
                "extracted_id": item_id,
            },
        )
        session.add(link)
        links_created += 1
        print(f"  ✓ Linked to: {item.type_name}")

    return links_created


async def main():
    """Process all documents to create AI-powered links."""
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--test", action="store_true", help="Test mode: process only first 5 documents"
    )
    args = parser.parse_args()

    if not AI_ENABLED:
        print("AI linking is disabled. Exiting.")
        return

    print("Starting AI document linking...")
    if args.test:
        print("TEST MODE: Processing only first 5 documents")
    print("=" * 60)

    total_processed = 0
    total_links = 0

    async with get_session() as session:
        # Fetch documents with content (skip error files)
        stmt = (
            select(DocumentModel)
            .where(~DocumentModel.title.ilike("%error%"))
            .order_by(DocumentModel.created_at)
        )
        if args.test:
            # In test mode, prioritize Quality/DB-related docs
            stmt = (
                select(DocumentModel)
                .where(
                    ~DocumentModel.title.ilike("%error%"),
                    DocumentModel.source_file.ilike("%Quality%"),
                )
                .order_by(DocumentModel.created_at)
                .limit(10)
            )
        result = await session.execute(stmt)
        documents = result.scalars().all()

        print(f"Found {len(documents)} documents to process.\n")

        for doc in documents:
            total_processed += 1
            print(f"[{total_processed}/{len(documents)}] Processing: {doc.title}")

            # Skip if no content
            if not doc.content or len(doc.content.strip()) < 50:
                print("  Skipping: No content")
                continue

            # Extract Item IDs using AI
            item_ids = await extract_item_ids_from_text(
                doc.content, model="gpt-4o-mini"
            )

            if not item_ids:
                print("  No Item IDs found")
                continue

            print(f"  Found IDs: {item_ids}")

            # Create links
            links_created = await link_document_to_items(
                session, doc, item_ids, "gpt-4o-mini"
            )
            total_links += links_created

            # Rate limiting (1 request per second)
            await asyncio.sleep(1)

        # Commit all changes
        await session.commit()

    print("\n" + "=" * 60)
    print("Processing complete!")
    print(f"Documents processed: {total_processed}")
    print(f"New links created: {total_links}")


if __name__ == "__main__":
    asyncio.run(main())
