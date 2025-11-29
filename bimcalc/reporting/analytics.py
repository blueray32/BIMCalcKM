from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any
from uuid import UUID

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from bimcalc.db.models import ItemModel, PriceItemModel, ProjectModel

class AnalyticsEngine:
    """Aggregates and analyzes project data for dashboard visualization."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_cost_trends(self, project_id: UUID) -> Dict[str, Any]:
        """Calculates cumulative project cost over time based on item creation."""
        # Group items by creation date
        query = (
            select(
                func.date_trunc('day', ItemModel.created_at).label('date'),
                func.sum(ItemModel.quantity * PriceItemModel.unit_price).label('daily_cost')
            )
            .join(PriceItemModel, ItemModel.price_item_id == PriceItemModel.id)
            .where(ItemModel.project_id == str(project_id))
            .group_by(func.date_trunc('day', ItemModel.created_at))
            .order_by('date')
        )
        
        result = await self.session.execute(query)
        rows = result.all()
        
        dates = []
        cumulative_costs = []
        running_total = Decimal(0)
        
        for row in rows:
            date_str = row.date.strftime('%Y-%m-%d')
            daily_cost = row.daily_cost or Decimal(0)
            running_total += daily_cost
            
            dates.append(date_str)
            cumulative_costs.append(float(running_total))
            
        return {
            "labels": dates,
            "datasets": [
                {
                    "label": "Cumulative Cost",
                    "data": cumulative_costs,
                    "borderColor": "#4F46E5", # Indigo-600
                    "backgroundColor": "rgba(79, 70, 229, 0.1)",
                    "fill": True
                }
            ]
        }

    async def get_category_distribution(self, project_id: UUID) -> Dict[str, Any]:
        """Calculates total cost distribution by category."""
        query = (
            select(
                ItemModel.category,
                func.sum(ItemModel.quantity * PriceItemModel.unit_price).label('total_cost')
            )
            .join(PriceItemModel, ItemModel.price_item_id == PriceItemModel.id)
            .where(ItemModel.project_id == str(project_id))
            .group_by(ItemModel.category)
            .order_by(desc('total_cost'))
        )
        
        result = await self.session.execute(query)
        rows = result.all()
        
        labels = []
        data = []
        
        for row in rows:
            category = row.category or "Uncategorized"
            cost = float(row.total_cost or 0)
            labels.append(category)
            data.append(cost)
            
        return {
            "labels": labels,
            "datasets": [{
                "data": data,
                "backgroundColor": [
                    "#4F46E5", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", 
                    "#EC4899", "#6366F1", "#14B8A6", "#F97316", "#64748B"
                ]
            }]
        }

    async def get_resource_utilization(self, project_id: UUID) -> Dict[str, Any]:
        """Calculates item count by family type (proxy for resource usage)."""
        query = (
            select(
                ItemModel.family,
                func.count(ItemModel.id).label('count')
            )
            .where(ItemModel.project_id == str(project_id))
            .group_by(ItemModel.family)
            .order_by(desc('count'))
            .limit(10) # Top 10 families
        )
        
        result = await self.session.execute(query)
        rows = result.all()
        
        labels = []
        data = []
        
        for row in rows:
            labels.append(row.family)
            data.append(row.count)
            
        return {
            "labels": labels,
            "datasets": [{
                "label": "Item Count",
                "data": data,
                "backgroundColor": "#10B981" # Emerald-500
            }]
        }
