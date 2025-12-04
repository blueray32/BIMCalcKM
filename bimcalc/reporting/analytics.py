from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any
from uuid import UUID

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from bimcalc.db.models import ItemModel, PriceItemModel


class AnalyticsEngine:
    """Aggregates and analyzes project data for dashboard visualization."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_cost_trends(self, project_id: UUID) -> Dict[str, Any]:
        """Calculates cumulative project cost over time based on item creation."""

        # Check dialect
        dialect = self.session.bind.dialect.name if self.session.bind else "sqlite"

        if dialect == "postgresql":
            date_col = func.date_trunc("day", ItemModel.created_at).label("date")
            group_by = func.date_trunc("day", ItemModel.created_at)
        else:
            # SQLite fallback
            date_col = func.date(ItemModel.created_at).label("date")
            group_by = func.date(ItemModel.created_at)

        # Group items by creation date
        query = (
            select(
                date_col,
                func.sum(ItemModel.quantity * PriceItemModel.unit_price).label(
                    "daily_cost"
                ),
            )
            .join(PriceItemModel, ItemModel.price_item_id == PriceItemModel.id)
            .where(ItemModel.project_id == str(project_id))
            .group_by("date")
            .order_by("date")
        )

        result = await self.session.execute(query)
        rows = result.all()

        dates = []
        cumulative_costs = []
        running_total = Decimal(0)

        for row in rows:
            if isinstance(row.date, str):
                date_str = row.date
            else:
                date_str = row.date.strftime("%Y-%m-%d")

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
                    "borderColor": "#4F46E5",  # Indigo-600
                    "backgroundColor": "rgba(79, 70, 229, 0.1)",
                    "fill": True,
                }
            ],
        }

    async def get_category_distribution(self, project_id: UUID) -> Dict[str, Any]:
        """Calculates total cost distribution by category."""
        query = (
            select(
                ItemModel.category,
                func.sum(ItemModel.quantity * PriceItemModel.unit_price).label(
                    "total_cost"
                ),
            )
            .join(PriceItemModel, ItemModel.price_item_id == PriceItemModel.id)
            .where(ItemModel.project_id == str(project_id))
            .group_by(ItemModel.category)
            .order_by(desc("total_cost"))
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
            "datasets": [
                {
                    "data": data,
                    "backgroundColor": [
                        "#4F46E5",
                        "#10B981",
                        "#F59E0B",
                        "#EF4444",
                        "#8B5CF6",
                        "#EC4899",
                        "#6366F1",
                        "#14B8A6",
                        "#F97316",
                        "#64748B",
                    ],
                }
            ],
        }

    async def get_resource_utilization(self, project_id: UUID) -> Dict[str, Any]:
        """Calculates item count by family type (proxy for resource usage)."""
        query = (
            select(ItemModel.family, func.count(ItemModel.id).label("count"))
            .where(ItemModel.project_id == str(project_id))
            .group_by(ItemModel.family)
            .order_by(desc("count"))
            .limit(10)  # Top 10 families
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
            "datasets": [
                {
                    "label": "Item Count",
                    "data": data,
                    "backgroundColor": "#10B981",  # Emerald-500
                }
            ],
        }

    async def get_item_price_history(
        self, item_code: str, org_id: str
    ) -> Dict[str, Any]:
        """Fetches historical price changes for a specific item code."""
        query = (
            select(
                PriceItemModel.unit_price,
                PriceItemModel.valid_from,
                PriceItemModel.valid_to,
                PriceItemModel.vendor_id,
            )
            .where(
                PriceItemModel.item_code == item_code, PriceItemModel.org_id == org_id
            )
            .order_by(PriceItemModel.valid_from)
        )

        result = await self.session.execute(query)
        rows = result.all()

        history = []
        for row in rows:
            history.append(
                {
                    "price": float(row.unit_price),
                    "date": row.valid_from.strftime("%Y-%m-%d"),
                    "vendor": row.vendor_id,
                }
            )

        return {"item_code": item_code, "history": history}

    async def compare_vendors(
        self, item_codes: List[str], org_id: str
    ) -> Dict[str, Any]:
        """Compares current prices for a list of items across vendors."""
        query = (
            select(
                PriceItemModel.vendor_id,
                func.sum(PriceItemModel.unit_price).label("total_cost"),
                func.count(PriceItemModel.id).label("item_count"),
            )
            .where(
                PriceItemModel.item_code.in_(item_codes),
                PriceItemModel.org_id == org_id,
                PriceItemModel.is_current == True,
            )
            .group_by(PriceItemModel.vendor_id)
        )

        result = await self.session.execute(query)
        rows = result.all()

        comparison = []
        for row in rows:
            comparison.append(
                {
                    "vendor": row.vendor_id,
                    "total_cost": float(row.total_cost),
                    "item_count": row.item_count,
                    "coverage_percent": (row.item_count / len(item_codes)) * 100
                    if item_codes
                    else 0,
                }
            )

        return {"comparison": comparison}

    async def forecast_cost_trends(
        self, project_id: UUID, days: int = 90
    ) -> Dict[str, Any]:
        """Simple linear forecast of project costs."""
        # Get daily cumulative costs (reuse existing logic logic or query)
        # For MVP, we'll use the get_cost_trends logic and extrapolate
        trends = await self.get_cost_trends(project_id)

        if not trends["datasets"][0]["data"]:
            return {"forecast": [], "message": "Not enough data to forecast"}

        data = trends["datasets"][0]["data"]
        labels = trends["labels"]

        # Simple Linear Regression (y = mx + c)
        n = len(data)
        if n < 2:
            return {"forecast": [], "message": "Need at least 2 data points"}

        x = list(range(n))
        y = data

        # Calculate slope (m) and intercept (c)
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(i * j for i, j in zip(x, y, strict=False))
        sum_xx = sum(i * i for i in x)

        m = (n * sum_xy - sum_x * sum_y) / (n * sum_xx - sum_x * sum_x)
        c = (sum_y - m * sum_x) / n

        # Forecast
        last_date = datetime.strptime(labels[-1], "%Y-%m-%d")
        forecast_data = []
        forecast_labels = []

        for i in range(1, days + 1):
            next_x = n - 1 + i
            next_y = m * next_x + c
            next_date = last_date + timedelta(days=i)

            forecast_data.append(max(0, next_y))  # No negative costs
            forecast_labels.append(next_date.strftime("%Y-%m-%d"))

        return {
            "original_labels": labels,
            "original_data": data,
            "forecast_labels": forecast_labels,
            "forecast_data": forecast_data,
            "trend_slope": m,
        }
