from datetime import datetime, timedelta
from statistics import linear_regression
from typing import List, Optional

from pydantic import BaseModel

from bimcalc.db.models import PriceItemModel


class TrendPoint(BaseModel):
    date: datetime
    price: float
    is_forecast: bool = False


class PriceTrend(BaseModel):
    slope: float
    intercept: float
    points: List[TrendPoint]
    forecast: List[TrendPoint]
    trend_description: str
    annual_change_percent: float


def predict_price_trend(history: List[PriceItemModel]) -> Optional[PriceTrend]:
    """
    Calculate linear trend from price history and forecast future prices.
    
    Args:
        history: List of PriceItemModel objects (should be sorted by date ideally, but we'll sort here)
        
    Returns:
        PriceTrend object or None if insufficient data
    """
    if len(history) < 2:
        return None
    
    # Sort by date ascending
    sorted_hist = sorted(history, key=lambda x: x.valid_from)
    
    # Prepare data
    # Use valid_from as the x-axis
    dates = [x.valid_from for x in sorted_hist]
    prices = [float(x.unit_price) for x in sorted_hist]
    
    # Convert dates to timestamps for regression (X axis)
    timestamps = []
    for d in dates:
        if isinstance(d, str):
            try:
                # Try ISO format first
                dt = datetime.fromisoformat(d)
            except ValueError:
                try:
                    # Try SQLite default format
                    dt = datetime.strptime(d, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    # Fallback or skip
                    continue
            timestamps.append(dt.timestamp())
        else:
            timestamps.append(d.timestamp())
    
    if len(timestamps) != len(prices):
        return None
    
    try:
        slope, intercept = linear_regression(timestamps, prices)
    except Exception:
        # Fallback for constant prices or errors
        if len(set(prices)) == 1:
            slope = 0.0
            intercept = prices[0]
        else:
            return None
        
    # Generate trend points for existing dates (The "Line of Best Fit")
    trend_points = []
    for d, ts in zip(dates, timestamps):
        trend_price = slope * ts + intercept
        trend_points.append(TrendPoint(date=d, price=trend_price))
        
    # Forecast next 12 months (monthly intervals)
    last_date = dates[-1]
    forecast_points = []
    for i in range(1, 13):
        future_date = last_date + timedelta(days=30 * i)
        future_ts = future_date.timestamp()
        future_price = slope * future_ts + intercept
        forecast_points.append(TrendPoint(date=future_date, price=future_price, is_forecast=True))
        
    # Calculate annual change
    seconds_per_year = 365.25 * 24 * 3600
    annual_change = slope * seconds_per_year
    current_price = prices[-1]
    
    if current_price != 0:
        annual_change_percent = (annual_change / current_price) * 100
    else:
        annual_change_percent = 0.0
        
    # Description
    if abs(annual_change_percent) < 0.5:
        desc = "Stable"
    elif annual_change_percent > 0:
        desc = f"Increasing (+{annual_change_percent:.1f}% / year)"
    else:
        desc = f"Decreasing ({annual_change_percent:.1f}% / year)"
        
    return PriceTrend(
        slope=slope,
        intercept=intercept,
        points=trend_points,
        forecast=forecast_points,
        trend_description=desc,
        annual_change_percent=annual_change_percent
    )
