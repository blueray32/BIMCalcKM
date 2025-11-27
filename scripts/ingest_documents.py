import sys
import os
import asyncio
import re
from uuid import uuid4
from datetime import datetime
from pypdf import PdfReader
from docx import Document as DocxDocument
import openai
from openai import AsyncOpenAI

# Add project root to path
sys.path.append(os.getcwd())

from bimcalc.db.connection import get_session
from bimcalc.db.models import DocumentModel, DocumentLinkModel, ItemModel
from sqlalchemy import select

# Configure OpenAI
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def get_embedding(text):
    if not client.api_key:
        return [0.0] * 1536 # Placeholder
    try:
        # Truncate text to avoid token limits (rough approx)
        truncated_text = text[:8000] 
        response = await client.embeddings.create(
            input=truncated_text,
            model="text-embedding-3-large",
            dimensions=1536
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Embedding error: {e}")
        return [0.0] * 1536

def extract_text(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    text = ""
    try:
        if ext == ".pdf":
            reader = PdfReader(file_path)
            for page in reader.pages:
                text += page.extract_text() + "\n"
        elif ext == ".docx":
            doc = DocxDocument(file_path)
            for para in doc.paragraphs:
                text += para.text + "\n"
        elif ext == ".txt":
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
    except Exception as e:
        print(f"Error extracting text from {file_path}: {e}")
    return text.strip()

def get_tags(file_path):
    tags = []
    path_lower = file_path.lower()
    if "manuals" in path_lower:
        tags.append("#Manuals")
    if "contracts" in path_lower:
        tags.append("#Contract")
    if "quality" in path_lower:
        tags.append("#QA")
    if "elec" in path_lower or "electrical" in path_lower:
        tags.append("#Electrical")
    if "mech" in path_lower or "mechanical" in path_lower:
        tags.append("#Mechanical")
    if "test report" in path_lower:
        tags.append("#TestReport")
    return tags

async def ingest_document(file_path, item_refs):
    print(f"Ingesting: {file_path}")
    text = extract_text(file_path)
    if not text:
        print("No text extracted. Skipping.")
        return

    tags = get_tags(file_path)
    embedding = await get_embedding(text)

    doc_id = uuid4()
    doc = DocumentModel(
        id=doc_id,
        title=os.path.basename(file_path),
        content=text,
        embedding=embedding,
        tags=tags,
        doc_type=os.path.splitext(file_path)[1].lower(),
        source_file=file_path,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    links = []
    # Link to items based on filename matching
    filename = os.path.basename(file_path)
    for ref, item_id in item_refs.items():
        # Simple case-insensitive substring match for now
        # Avoid short matches like "DB" matching everything
        if len(ref) > 3 and ref.lower() in filename.lower():
            print(f"  -> Linking to Item: {ref}")
            link = DocumentLinkModel(
                id=uuid4(),
                item_id=item_id,
                document_id=doc_id,
                link_type="auto_match",
                confidence=0.8
            )
            links.append(link)

    async with get_session() as session:
        session.add(doc)
        for link in links:
            session.add(link)
        await session.commit()
        print("Saved document and links.")

async def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/ingest_documents.py <directory> ...")
        sys.exit(1)

    # Fetch all item references for linking
    print("Fetching item references...")
    item_refs = {}
    async with get_session() as session:
        result = await session.execute(
            select(ItemModel.id, ItemModel.type_name)
            .where(ItemModel.project_id == 'tritex24-229')
        )
        for row in result:
            item_refs[row.type_name] = row.id
    print(f"Loaded {len(item_refs)} item references.")

    files_to_process = []
    for path in sys.argv[1:]:
        if os.path.isdir(path):
            for root, _, files in os.walk(path):
                for file in files:
                    if file.lower().endswith((".pdf", ".docx", ".txt")) and not file.startswith("~$"):
                        files_to_process.append(os.path.join(root, file))
        else:
            files_to_process.append(path)

    print(f"Found {len(files_to_process)} documents.")
    for file_path in files_to_process:
        await ingest_document(file_path, item_refs)

if __name__ == "__main__":
    asyncio.run(main())
