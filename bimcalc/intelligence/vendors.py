"""Vendor Intelligence module for analyzing quotes and invoices."""

import json
import logging
from typing import Any

import openai
import httpx
from pypdf import PdfReader
from io import BytesIO

logger = logging.getLogger(__name__)


class VendorAnalyzer:
    """Analyzes vendor documents (PDFs) to extract pricing data."""

    SYSTEM_PROMPT = """You are a procurement expert specializing in extracting structured data from vendor quotes and invoices.

Your task is to extract line items, descriptions, quantities, unit prices, and total prices from the provided document text.

Return a JSON object with this exact structure:
{
  "items": [
    {
      "vendor_code": "SKU or Item Code",
      "description": "Full item description",
      "quantity": 1.0,
      "unit": "each|m|m2|kg",
      "unit_price": 10.50,
      "total_price": 10.50,
      "currency": "EUR|GBP|USD",
      "confidence": 0.95
    }
  ],
  "metadata": {
    "vendor_name": "Detected Vendor Name",
    "document_date": "YYYY-MM-DD",
    "document_number": "Quote/Invoice Number"
  }
}

Rules:
- Extract ALL line items found in the table.
- Normalize units to standard BIM units (each, m, m2, m3, kg) where possible.
- If a field is missing, use null.
- Confidence score (0.0-1.0) should reflect your certainty about the extraction quality.
"""

    async def fetch_and_analyze_url(self, url: str) -> dict[str, Any]:
        """Download PDF from URL and analyze it."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, follow_redirects=True)
                response.raise_for_status()
                content = response.content

            return await self.extract_quote_data(content, url.split("/")[-1])
        except Exception as e:
            logger.error(f"Failed to fetch PDF from {url}: {e}")
            return {"error": f"Download failed: {str(e)}"}

    async def extract_quote_data(
        self, file_content: bytes, filename: str
    ) -> dict[str, Any]:
        """Extract structured data from a quote/invoice file.

        Args:
            file_content: Raw bytes of the uploaded file
            filename: Name of the file

        Returns:
            Dict containing extracted items and metadata
        """
        try:
            # 1. Extract text from PDF
            text_content = self._extract_text_from_pdf(file_content)
            if not text_content:
                return {"error": "Could not extract text from document"}

            # 2. Call LLM to analyze text
            analysis_result = await self._call_llm(text_content)

            # 3. Parse response
            return self._parse_response(analysis_result)

        except Exception as e:
            logger.error(f"Failed to analyze quote {filename}: {e}")
            return {"error": str(e)}

    def _extract_text_from_pdf(self, file_content: bytes) -> str:
        """Extract text content from PDF bytes."""
        try:
            reader = PdfReader(BytesIO(file_content))
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text
        except Exception as e:
            logger.error(f"PDF extraction error: {e}")
            return ""

    async def _call_llm(self, context: str) -> str:
        """Call OpenAI to analyze document text."""
        client = openai.AsyncOpenAI()

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Analyze this document text:\n\n{context[:10000]}",
                },  # Limit context window
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )

        return response.choices[0].message.content or "{}"

    def _parse_response(self, llm_response: str) -> dict:
        """Parse and validate LLM response."""
        try:
            return json.loads(llm_response)
        except json.JSONDecodeError:
            logger.error("Failed to parse LLM response as JSON")
            return {"items": [], "metadata": {}, "error": "Invalid AI response"}
