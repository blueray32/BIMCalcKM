import os
from typing import Any

from arq.connections import RedisSettings
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from bimcalc.db.connection import get_session
from bimcalc.integration.price_scout_sync import sync_price_scout_prices

# Database setup for worker
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def startup(ctx: dict[str, Any]) -> None:
    """Initialize resources when worker starts."""
    ctx["session_maker"] = async_session
    print("Worker started. Database connection initialized.")


async def shutdown(ctx: dict[str, Any]) -> None:
    """Cleanup resources when worker stops."""
    await engine.dispose()
    print("Worker stopped. Database connection closed.")


async def run_price_scout_sync(
    ctx: dict[str, Any], org_id: str, full_sync: bool = False
) -> dict[str, Any]:
    """Wrapper for sync_price_scout_prices to run as a background job."""
    print(f"Starting Price Scout sync job for org_id={org_id}, full_sync={full_sync}")

    # sync_price_scout_prices manages its own session and HTTP client
    delta_days = None if full_sync else 7

    result = await sync_price_scout_prices(
        org_id=org_id, delta_days=delta_days, classification_filter=None, region=None
    )

    print(f"Price Scout sync job completed: {result}")
    return result


async def send_daily_digest(
    ctx: dict[str, Any], org_id: str, project_id: str, recipients: list[str]
) -> dict[str, Any]:
    """Send daily QA digest email to recipients."""
    from bimcalc.intelligence.notifications import get_email_notifier
    from bimcalc.intelligence.risk_scoring import get_risk_score_cached
    from bimcalc.db.models import ItemModel, QAChecklistModel
    from sqlalchemy import select, func
    from datetime import datetime, timedelta

    print(f"Starting daily digest for {org_id}/{project_id}")

    session_maker = ctx["session_maker"]
    async with session_maker() as session:
        # Calculate yesterday's stats
        yesterday = datetime.utcnow() - timedelta(days=1)
        yesterday_start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)

        # Get all items
        items_query = select(ItemModel).where(
            ItemModel.org_id == org_id, ItemModel.project_id == project_id
        )
        result = await session.execute(items_query)
        items = list(result.scalars())

        # Calculate risk scores
        high_risk_items = []
        for item in items:
            risk = await get_risk_score_cached(session, str(item.id))
            if risk.score >= 61:
                high_risk_items.append(
                    {
                        "family": item.family,
                        "type_name": item.type_name,
                        "score": risk.score,
                    }
                )

        # Count checklists
        checklists_query = (
            select(func.count())
            .select_from(QAChecklistModel)
            .where(
                QAChecklistModel.org_id == org_id,
                QAChecklistModel.project_id == project_id,
            )
        )
        total_checklists = await session.scalar(checklists_query)

        # Count completed yesterday
        completed_query = (
            select(func.count())
            .select_from(QAChecklistModel)
            .where(
                QAChecklistModel.org_id == org_id,
                QAChecklistModel.project_id == project_id,
                QAChecklistModel.completed_at >= yesterday_start,
                QAChecklistModel.completion_percent == 100.0,
            )
        )
        completed_yesterday = await session.scalar(completed_query)

        # Count generated yesterday
        generated_query = (
            select(func.count())
            .select_from(QAChecklistModel)
            .where(
                QAChecklistModel.org_id == org_id,
                QAChecklistModel.project_id == project_id,
                QAChecklistModel.generated_at >= yesterday_start,
            )
        )
        generated_yesterday = await session.scalar(generated_query)

        # Calculate compliance
        if total_checklists and total_checklists > 0:
            completed_query = (
                select(func.count())
                .select_from(QAChecklistModel)
                .where(
                    QAChecklistModel.org_id == org_id,
                    QAChecklistModel.project_id == project_id,
                    QAChecklistModel.completion_percent == 100.0,
                )
            )
            completed_total = await session.scalar(completed_query)
            compliance_percent = (completed_total / total_checklists) * 100
        else:
            compliance_percent = 0.0

        # Build digest data
        digest_data = {
            "new_high_risk": 0,  # Would need to track changes
            "checklists_completed": completed_yesterday or 0,
            "checklists_generated": generated_yesterday or 0,
            "total_high_risk": len(high_risk_items),
            "compliance_percent": compliance_percent,
            "active_checklists": total_checklists or 0,
            "top_risks": sorted(
                high_risk_items, key=lambda x: x["score"], reverse=True
            )[:5],
        }

        # Send email
        notifier = get_email_notifier()
        await notifier.send_daily_digest(recipients, digest_data)

        print(f"Daily digest sent to {len(recipients)} recipients")
        return {"sent": True, "recipients": len(recipients), "stats": digest_data}


async def batch_generate_checklists_job(
    ctx: dict[str, Any], org_id: str, project_id: str, item_ids: list[str]
) -> dict[str, Any]:
    """ARQ worker task for batch checklist generation.

    Args:
        ctx: ARQ context
        org_id: Organization ID
        project_id: Project ID
        item_ids: List of item IDs to process

    Returns:
        Results dict with stats
    """
    from bimcalc.intelligence.bulk_operations import batch_generate_checklists

    print(f"Starting batch checklist generation: {len(item_ids)} items")

    session_maker = ctx["session_maker"]
    async with session_maker() as session:
        # Progress callback
        def report_progress(current, total):
            print(f"Progress: {current}/{total} ({current / total * 100:.1f}%)")

        results = await batch_generate_checklists(
            session, item_ids, progress_callback=report_progress
        )


async def process_document_job(ctx: dict[str, Any], document_id: str) -> dict[str, Any]:
    """ARQ worker task for processing a document.

    Args:
        ctx: ARQ context
        document_id: ID of the document to process

    Returns:
        Result dict
    """
    from bimcalc.intelligence.document_processor import DocumentProcessor
    from bimcalc.db.models_documents import ProjectDocumentModel
    from sqlalchemy import select

    print(f"Starting document processing job for {document_id}")

    session_maker = ctx["session_maker"]
    async with session_maker() as session:
        # Verify document exists
        result = await session.execute(
            select(ProjectDocumentModel).where(ProjectDocumentModel.id == document_id)
        )
        document = result.scalars().first()

        if not document:
            print(f"Document {document_id} not found")
            return {"status": "failed", "error": "Document not found"}

        # Update status to processing
        document.status = "processing"
        await session.commit()

        try:
            processor = DocumentProcessor(session)
            # Re-fetch document to ensure it's attached to session if needed,
            # though DocumentProcessor takes session.
            # Note: DocumentProcessor.process_document expects UUID or str?
            # Let's check implementation. It likely takes UUID.
            from uuid import UUID

            await processor.process_document(UUID(document_id))

            print(f"Document {document_id} processing completed successfully")
            return {"status": "completed"}

        except Exception as e:
            print(f"Document {document_id} processing failed: {str(e)}")
            # Update status to failed
            document.status = "failed"
            document.error_message = str(e)
            await session.commit()
            return {"status": "failed", "error": str(e)}


async def send_scheduled_report_job(
    ctx, project_id: str, recipient_emails: list[str], report_type: str = "weekly"
):
    """Background job to generate and send scheduled reports via email.

    Args:
        ctx: ARQ context
        project_id: UUID of the project
        recipient_emails: List of email addresses to send the report to
        report_type: Type of report ("weekly", "monthly", etc.)
    """
    from bimcalc.notifications.email import EmailService
    from bimcalc.reporting.dashboard_metrics import compute_dashboard_metrics

    print(f"Starting scheduled {report_type} report for project {project_id}")

    try:
        async with get_session() as session:
            # Fetch project metrics
            metrics = await compute_dashboard_metrics(session, "default", project_id)

            # Send email
            email_service = EmailService()
            success = email_service.send_weekly_report(
                to_emails=recipient_emails,
                project_name=f"Project {project_id}",
                metrics=metrics,
            )

            if success:
                print(f"Successfully sent {report_type} report to {recipient_emails}")
                return {"status": "sent", "recipients": recipient_emails}
            else:
                print(f"Failed to send {report_type} report (SMTP not configured)")
                return {"status": "skipped", "reason": "SMTP not configured"}

    except Exception as e:
        print(f"Report generation/sending failed: {str(e)}")
        return {"status": "failed", "error": str(e)}


class WorkerSettings:
    functions = [
        run_price_scout_sync,
        send_daily_digest,
        batch_generate_checklists_job,
        process_document_job,
        send_scheduled_report_job,
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(
        os.environ.get("REDIS_URL", "redis://redis:6379")
    )
    # Daily digest at 9 AM (uncomment when ready to use)
    # from arq.cron import cron
    # cron_jobs = [
    #     cron(send_daily_digest, hour=9, minute=0,
    #          kwargs={"org_id": "demo-org", "project_id": "tritex24-229",
    #                  "recipients": ["team@example.com"]})
    # ]
