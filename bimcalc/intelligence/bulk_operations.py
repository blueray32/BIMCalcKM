"""Bulk operations for batch processing Intelligence features."""

import zipfile
from io import BytesIO
from uuid import UUID
import logging

from bimcalc.intelligence.exports import ChecklistPDFExporter
from bimcalc.db.models import ItemModel, QAChecklistModel

logger = logging.getLogger(__name__)


async def batch_generate_checklists(
    session,
    item_ids: list[str],
    progress_callback=None
) -> dict:
    """Generate checklists for multiple items in batch.
    
    Args:
        session: Database session
        item_ids: List of item IDs to process
        progress_callback: Optional function to report progress
        
    Returns:
        Dict with results and stats
    """
    from bimcalc.intelligence.checklist_generator import QAChecklistGenerator, calculate_completion_percent
    from bimcalc.intelligence.recommendations import get_document_recommendations
    from sqlalchemy import select
    
    generator = QAChecklistGenerator()
    results = {
        "total": len(item_ids),
        "successful": 0,
        "failed": 0,
        "skipped": 0,
        "checklists": []
    }
    
    for idx, item_id in enumerate(item_ids):
        try:
            # Report progress
            if progress_callback:
                progress_callback(idx + 1, len(item_ids))
            
            # Check if checklist already exists
            existing_query = select(QAChecklistModel).where(
                QAChecklistModel.item_id == UUID(item_id)
            )
            existing_result = await session.execute(existing_query)
            if existing_result.scalar_one_or_none():
                results["skipped"] += 1
                logger.info(f"Skipped {item_id} - checklist already exists")
                continue
            
            # Get item
            item = await session.get(ItemModel, UUID(item_id))
            if not item:
                results["failed"] += 1
                logger.warning(f"Item {item_id} not found")
                continue
            
            # Get recommendations
            recommendations = await get_document_recommendations(
                session, item_id, limit=5, min_score=0.6
            )
            
            if not recommendations:
                results["failed"] += 1
                logger.warning(f"No documents found for {item_id}")
                continue
            
            # Get document objects
            from bimcalc.db.models import DocumentModel
            doc_ids = [rec["document_id"] for rec in recommendations]
            docs_query = select(DocumentModel).where(DocumentModel.id.in_(doc_ids))
            docs_result = await session.execute(docs_query)
            quality_docs = list(docs_result.scalars())
            
            # Generate checklist
            checklist_data = await generator.generate_checklist(item, quality_docs)
            
            if not checklist_data.get("items"):
                results["failed"] += 1
                logger.warning(f"Failed to generate checklist for {item_id}")
                continue
            
            # Save to database
            checklist = QAChecklistModel(
                item_id=UUID(item_id),
                org_id=item.org_id,
                project_id=item.project_id,
                checklist_items={"items": checklist_data["items"]},
                source_documents={"docs": checklist_data["source_docs"]},
                auto_generated=True,
                completion_percent=0.0,
                created_by="batch_system"
            )
            
            session.add(checklist)
            await session.flush()
            
            results["successful"] += 1
            results["checklists"].append({
                "item_id": item_id,
                "checklist_id": str(checklist.id),
                "items_count": len(checklist_data["items"])
            })
            
            logger.info(f"Generated checklist for {item_id}")
            
        except Exception as e:
            results["failed"] += 1
            logger.error(f"Error generating checklist for {item_id}: {e}")
    
    # Commit all changes
    await session.commit()
    
    return results


async def bulk_assess_risks(
    session,
    org_id: str,
    project_id: str
) -> dict:
    """Calculate risk scores for all items in project.
    
    Args:
        session: Database session
        org_id: Organization ID
        project_id: Project ID
        
    Returns:
        Dict with risk assessment results
    """
    from bimcalc.intelligence.risk_scoring import get_risk_score_cached
    from sqlalchemy import select
    
    # Get all items
    query = select(ItemModel).where(
        ItemModel.org_id == org_id,
        ItemModel.project_id == project_id
    )
    result = await session.execute(query)
    items = list(result.scalars())
    
    risk_results = {
        "total_items": len(items),
        "high_risk": [],
        "medium_risk": [],
        "low_risk": [],
        "avg_score": 0.0
    }
    
    total_score = 0.0
    
    for item in items:
        try:
            risk = await get_risk_score_cached(session, str(item.id))
            
            item_risk = {
                "item_id": str(item.id),
                "family": item.family,
                "type_name": item.type_name,
                "score": risk.score,
                "level": risk.level
            }
            
            if risk.level == "High":
                risk_results["high_risk"].append(item_risk)
            elif risk.level == "Medium":
                risk_results["medium_risk"].append(item_risk)
            else:
                risk_results["low_risk"].append(item_risk)
            
            total_score += risk.score
            
        except Exception as e:
            logger.error(f"Error assessing risk for item {item.id}: {e}")
    
    if len(items) > 0:
        risk_results["avg_score"] = total_score / len(items)
    
    # Sort by score
    risk_results["high_risk"].sort(key=lambda x: x["score"], reverse=True)
    risk_results["medium_risk"].sort(key=lambda x: x["score"], reverse=True)
    
    return risk_results


async def export_all_checklists_zip(
    session,
    org_id: str,
    project_id: str
) -> bytes:
    """Export all checklists as ZIP file.
    
    Args:
        session: Database session
        org_id: Organization ID
        project_id: Project ID
        
    Returns:
        ZIP file as bytes
    """
    from sqlalchemy import select
    
    # Get all checklists for project
    query = select(QAChecklistModel).where(
        QAChecklistModel.org_id == org_id,
        QAChecklistModel.project_id == project_id
    )
    result = await session.execute(query)
    checklists = list(result.scalars())
    
    if not checklists:
        raise ValueError("No checklists found for this project")
    
    # Create ZIP file in memory
    zip_buffer = BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        exporter = ChecklistPDFExporter()
        
        for checklist in checklists:
            try:
                # Get associated item
                item = await session.get(ItemModel, checklist.item_id)
                if not item:
                    logger.warning(f"Item not found for checklist {checklist.id}")
                    continue
                
                # Generate PDF
                pdf_bytes = exporter.export(checklist, item)
                
                # Add to ZIP with descriptive filename
                safe_family = item.family.replace(" ", "_").replace("/", "-")[:50]
                safe_type = item.type_name.replace(" ", "_").replace("/", "-")[:50]
                filename = f"{safe_family}_{safe_type}_{checklist.id}.pdf"
                
                zip_file.writestr(filename, pdf_bytes)
                logger.info(f"Added {filename} to ZIP")
                
            except Exception as e:
                logger.error(f"Error exporting checklist {checklist.id}: {e}")
    
    zip_buffer.seek(0)
    return zip_buffer.getvalue()
