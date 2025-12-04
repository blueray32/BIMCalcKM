import os
from datetime import datetime
from uuid import uuid4
import aiofiles

try:
    import pdfplumber
except ImportError:
    pdfplumber = None
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import UploadFile

from bimcalc.db.models_documents import ProjectDocumentModel, ExtractedItemModel

UPLOAD_DIR = "uploads"


class DocumentProcessor:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def ingest_document(
        self, file: UploadFile, org_id: str, project_id: str
    ) -> ProjectDocumentModel:
        """Save uploaded file and create database record."""
        file_id = uuid4()
        filename = file.filename
        file_ext = os.path.splitext(filename)[1].lower()

        # Ensure upload directory exists
        os.makedirs(UPLOAD_DIR, exist_ok=True)

        file_path = os.path.join(UPLOAD_DIR, f"{file_id}{file_ext}")

        # Save file to disk
        async with aiofiles.open(file_path, "wb") as out_file:
            content = await file.read()
            await out_file.write(content)
            file_size = len(content)

        # Create DB record
        document = ProjectDocumentModel(
            id=file_id,
            org_id=org_id,
            project_id=project_id,
            filename=filename,
            file_path=file_path,
            file_type=file.content_type or "application/octet-stream",
            file_size_bytes=file_size,
            status="pending",
        )
        self.db.add(document)
        await self.db.commit()
        await self.db.refresh(document)

        return document

    async def process_document(self, document_id: str):
        """Extract text and items from the document."""
        document = await self.db.get(ProjectDocumentModel, document_id)
        if not document:
            raise ValueError("Document not found")

        document.status = "processing"
        await self.db.commit()

        try:
            extracted_items = []
            if (
                document.file_type == "application/pdf"
                or document.filename.lower().endswith(".pdf")
            ):
                extracted_items = self._process_pdf(document.file_path)
            else:
                # TODO: Handle Excel/CSV
                pass

            # Save extracted items
            for item_data in extracted_items:
                item = ExtractedItemModel(document_id=document.id, **item_data)
                self.db.add(item)

            document.status = "completed"
            document.processed_at = datetime.now()
            await self.db.commit()

        except Exception as e:
            document.status = "failed"
            document.error_message = str(e)
            await self.db.commit()
            raise e

    def _process_pdf(self, file_path: str) -> list[dict]:
        """Extract items from PDF using pdfplumber."""
        if pdfplumber is None:
            return []

        items = []
        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                # Try to extract tables first
                tables = page.extract_tables()
                if tables:
                    for table in tables:
                        items.extend(self._parse_table(table, page_num))
                else:
                    # Fallback to text extraction (simple line parsing)
                    text = page.extract_text()
                    items.extend(self._parse_text(text, page_num))
        return items

    def _parse_table(self, table: list[list[str]], page_num: int) -> list[dict]:
        """Heuristic parsing of table rows."""
        items = []
        headers = []
        # Simple heuristic: assume first row is header if it contains keywords
        if table and any(
            k in str(table[0]).lower()
            for k in ["description", "item", "qty", "quantity", "price", "cost"]
        ):
            headers = [h.lower() if h else "" for h in table[0]]
            rows = table[1:]
        else:
            rows = table

        for row in rows:
            # Skip empty rows
            if not any(row):
                continue

            item = {
                "raw_text": " | ".join([c for c in row if c]),
                "page_number": page_num,
                "confidence_score": 0.5,  # Default confidence
            }

            # Try to map columns based on headers or position
            # This is very basic and would need refinement for real-world docs
            description = ""
            quantity = None
            unit_price = None
            total_price = None
            unit = None

            for i, cell in enumerate(row):
                if not cell:
                    continue
                val = cell.strip()

                # If we have headers, use them
                if i < len(headers):
                    header = headers[i]
                    if "desc" in header or "item" in header:
                        description = val
                    elif "qty" in header or "quantity" in header:
                        quantity = self._parse_number(val)
                    elif "unit" in header and "price" not in header:
                        unit = val
                    elif "price" in header or "rate" in header:
                        unit_price = self._parse_number(val)
                    elif "total" in header or "amount" in header:
                        total_price = self._parse_number(val)
                else:
                    # Fallback: guess based on content
                    if not description and len(val) > 10 and not self._is_number(val):
                        description = val
                    elif quantity is None and self._is_number(val):
                        quantity = self._parse_number(val)
                    elif unit_price is None and self._is_number(val):
                        unit_price = self._parse_number(val)

            if description:
                item["description"] = description
                item["quantity"] = quantity
                item["unit"] = unit
                item["unit_price"] = unit_price
                item["total_price"] = total_price
                if quantity and unit_price:
                    item["confidence_score"] = 0.8

                items.append(item)

        return items

    def _parse_text(self, text: str, page_num: int) -> list[dict]:
        """Fallback text parsing."""
        items = []
        lines = text.split("\n")
        for line in lines:
            # Look for lines that look like line items: "Description ... 10 ... $50.00"
            # Very naive implementation
            parts = line.split()
            if len(parts) > 3:
                # Check if last parts are numbers
                if self._is_number(parts[-1]) and self._is_number(parts[-2]):
                    item = {
                        "raw_text": line,
                        "page_number": page_num,
                        "description": " ".join(parts[:-2]),
                        "quantity": self._parse_number(parts[-2]),
                        "total_price": self._parse_number(parts[-1]),
                        "confidence_score": 0.4,
                    }
                    items.append(item)
        return items

    def _is_number(self, s: str) -> bool:
        try:
            float(s.replace("$", "").replace(",", ""))
            return True
        except Exception:
            return False

    def _parse_number(self, s: str) -> float | None:
        try:
            return float(s.replace("$", "").replace(",", ""))
        except Exception:
            return None
