from typing import List, Dict, Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bimcalc.db.models_reporting import ReportTemplateModel
from bimcalc.reporting.analytics import AnalyticsEngine


class ReportBuilder:
    """Service for managing report templates and generating reports."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.analytics = AnalyticsEngine(db)

    async def create_template(
        self, org_id: str, name: str, config: Dict[str, Any], project_id: str = None
    ) -> ReportTemplateModel:
        """Create a new report template."""
        template = ReportTemplateModel(
            org_id=org_id, project_id=project_id, name=name, configuration=config
        )
        self.db.add(template)
        await self.db.commit()
        await self.db.refresh(template)
        return template

    async def get_templates(
        self, org_id: str, project_id: str = None
    ) -> List[ReportTemplateModel]:
        """Get available templates for an org/project."""
        query = select(ReportTemplateModel).where(ReportTemplateModel.org_id == org_id)

        if project_id:
            # Include project-specific templates OR global org templates
            query = query.where(
                (ReportTemplateModel.project_id == project_id)
                | (ReportTemplateModel.project_id.is_(None))
            )
        else:
            query = query.where(ReportTemplateModel.project_id.is_(None))

        result = await self.db.execute(query)
        return result.scalars().all()

    async def generate_report_data(
        self, project_id: UUID, template_id: UUID
    ) -> Dict[str, Any]:
        """Gather all data required for the report based on template config."""
        template = await self.db.get(ReportTemplateModel, template_id)
        if not template:
            raise ValueError("Template not found")

        config = template.configuration
        sections = config.get("sections", [])

        report_data = {
            "project_id": str(project_id),
            "generated_at": str(datetime.now()),
            "sections": {},
        }

        # Gather data for selected sections
        if "cost_trends" in sections:
            report_data["sections"][
                "cost_trends"
            ] = await self.analytics.get_cost_trends(project_id)

        if "category_distribution" in sections:
            report_data["sections"][
                "category_distribution"
            ] = await self.analytics.get_category_distribution(project_id)

        if "resource_utilization" in sections:
            report_data["sections"][
                "resource_utilization"
            ] = await self.analytics.get_resource_utilization(project_id)

        # Add more sections as needed (e.g., risk, compliance)

        return report_data

    # Future: generate_pdf(data), generate_excel(data)


import pandas as pd
from datetime import datetime, timezone
from sqlalchemy import and_

from bimcalc.db.models import ItemModel, ItemMappingModel, PriceItemModel


async def generate_report(
    session: AsyncSession,
    org_id: str,
    project_id: str,
    as_of: datetime | None = None,
) -> pd.DataFrame:
    """Generate cost report with as-of temporal query.

    Args:
        session: Database session
        org_id: Organization ID
        project_id: Project ID
        as_of: Timestamp for temporal query (default: now)

    Returns:
        DataFrame with report data
    """
    if as_of is None:
        as_of = datetime.now(timezone.utc)

    # Query: Items -> Mapping (SCD2 as-of) -> Price
    stmt = (
        select(
            ItemModel.family,
            ItemModel.type_name,
            ItemModel.quantity,
            ItemModel.unit,
            PriceItemModel.sku,
            PriceItemModel.description,
            PriceItemModel.unit_price,
            PriceItemModel.currency,
            PriceItemModel.vat_rate,
        )
        .select_from(ItemModel)
        .join(
            ItemMappingModel,
            and_(
                ItemMappingModel.org_id == ItemModel.org_id,
                ItemMappingModel.canonical_key == ItemModel.canonical_key,
                ItemMappingModel.start_ts <= as_of,
                (ItemMappingModel.end_ts.is_(None)) | (ItemMappingModel.end_ts > as_of),
            ),
            isouter=True,  # Left join to include unmatched items
        )
        .join(
            PriceItemModel,
            ItemMappingModel.price_item_id == PriceItemModel.id,
            isouter=True,
        )
        .where(
            ItemModel.org_id == org_id,
            ItemModel.project_id == project_id,
        )
    )

    result = await session.execute(stmt)
    rows = result.all()

    data = []
    for row in rows:
        qty = float(row.quantity or 0)
        price = float(row.unit_price or 0)
        vat = float(row.vat_rate or 0)

        net = qty * price
        gross = net * (1 + vat)

        data.append(
            {
                "family": row.family,
                "type": row.type_name,
                "quantity": qty,
                "unit": row.unit,
                "sku": row.sku,
                "description": row.description,
                "unit_price": price,
                "currency": row.currency,
                "vat_rate": vat,
                "total_net": net,
                "total_gross": gross,
            }
        )

    return pd.DataFrame(data)
