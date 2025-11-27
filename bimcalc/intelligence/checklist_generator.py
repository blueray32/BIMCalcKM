"""Auto-generate QA testing checklists using LLMs."""

import json
import logging
from typing import Any

import openai

from bimcalc.db.models import DocumentModel, ItemModel
from bimcalc.utils.redis_cache import get_cached, set_cached

logger = logging.getLogger(__name__)

# Cache TTL for generated checklists (stored in DB, not Redis)
CHECKLIST_CACHE_TTL = 86400  # 24 hours


class QAChecklistGenerator:
    """Generate QA testing checklists using LLM analysis of quality documents."""
    
    SYSTEM_PROMPT = """You are a construction QA expert specializing in generating comprehensive testing checklists.

Your task is to extract testable requirements from quality and safety documents for specific construction items.

Return a JSON object with this exact structure:
{
  "items": [
    {
      "id": 1,
      "requirement": "Clear, testable requirement statement",
      "category": "Inspection|Testing|Safety|Installation|Documentation",
      "priority": "High|Medium|Low",
      "estimated_time_minutes": 15
    }
  ]
}

Each requirement must be:
- Specific and actionable
- Testable (can answer yes/no or pass/fail)
- Relevant to the item type
- Based on the provided documents"""
    
    async def generate_checklist(
        self,
        item: ItemModel,
        quality_docs: list[DocumentModel]
    ) -> dict[str, Any]:
        """Generate QA checklist for item from quality documents.
        
        Args:
            item: Item to generate checklist for
            quality_docs: Relevant quality/safety documents
            
        Returns:
            Dict with 'items' (checklist items) and 'source_docs' (document refs)
        """
        try:
            # 1. Build context from item and documents
            context = self._build_context(item, quality_docs)
            
            # 2. Call LLM to generate checklist
            checklist_data = await self._call_llm(context)
            
            # 3. Parse and validate response
            checklist_items = self._parse_checklist(checklist_data)
            
            return {
                "items": checklist_items,
                "source_docs": [
                    {
                        "id": str(doc.id),
                        "title": doc.title,
                        "type": doc.doc_type or "unknown"
                    }
                    for doc in quality_docs
                ]
            }
        except Exception as e:
            logger.error(f"Failed to generate checklist for item {item.id}: {e}")
            # Return empty checklist on error
            return {"items": [], "source_docs": []}
    
    def _build_context(self, item: ItemModel, docs: list[DocumentModel]) -> str:
        """Build prompt context from item and documents.
        
        Args:
            item: Item details
            docs: Quality documents
            
        Returns:
            Formatted context string for LLM
        """
        context = f"""ITEM DETAILS:
- Type: {item.family} {item.type_name}
- Classification: {item.classification_code or 'Unknown'}
- Category: {item.category or 'Unknown'}
- Description: {getattr(item, 'description', 'N/A')}

QUALITY DOCUMENTS:
"""
        
        for doc in docs:
            # Include relevant excerpt (limit to 500 chars to save tokens)
            excerpt = doc.content[:500] + "..." if doc.content and len(doc.content) > 500 else (doc.content or "")
            context += f"\n--- {doc.title} ({doc.doc_type or 'document'}) ---\n{excerpt}\n"
        
        return context
    
    async def _call_llm(self, context: str) -> str:
        """Call OpenAI to generate checklist.
        
        Args:
            context: Formatted context with item and document info
            
        Returns:
            JSON string from LLM
        """
        client = openai.AsyncOpenAI()
        
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": f"""
Based on the following item details and quality documents, generate a comprehensive QA testing checklist.

{context}

Focus on:
1. Visual inspection requirements
2. Functional testing procedures
3. Safety compliance checks
4. Installation verification
5. Documentation requirements

Generate 5-10 checklist items that are specific, testable, and relevant to this item type.
"""}
            ],
            temperature=0.3,  # Lower temp for consistency
            response_format={"type": "json_object"}
        )
        
        return response.choices[0].message.content or "{}"
    
    def _parse_checklist(self, llm_response: str) -> list[dict]:
        """Parse and validate LLM response.
        
        Args:
            llm_response: JSON string from LLM
            
        Returns:
            List of validated checklist items
        """
        try:
            data = json.loads(llm_response)
            items = data.get("items", [])
            
            # Validate and normalize each item
            validated_items = []
            for idx, item in enumerate(items, 1):
                # Ensure required fields
                if "requirement" not in item:
                    logger.warning(f"Skipping item {idx}: missing 'requirement' field")
                    continue
                
                validated_item = {
                    "id": item.get("id", idx),
                    "requirement": item["requirement"],
                    "category": item.get("category", "General"),
                    "priority": item.get("priority", "Medium"),
                    "estimated_time_minutes": item.get("estimated_time_minutes", 10),
                    "completed": False,  # Always start uncompleted
                    "notes": ""
                }
                
                validated_items.append(validated_item)
            
            return validated_items
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.debug(f"Raw response: {llm_response}")
            return []
        except Exception as e:
            logger.error(f"Failed to parse checklist: {e}")
            return []


def calculate_completion_percent(checklist_items: list[dict]) -> float:
    """Calculate completion percentage from checklist items.
    
    Args:
        checklist_items: List of checklist items with 'completed' field
        
    Returns:
        Completion percentage (0-100)
    """
    if not checklist_items:
        return 0.0
    
    completed_count = sum(1 for item in checklist_items if item.get("completed", False))
    return round((completed_count / len(checklist_items)) * 100, 2)
