"""Prediction schemas for request/response validation."""

from datetime import date as date_type
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, Field


class ForecastResponse(BaseModel):
    """Schema for expense forecast response."""

    category: str
    predictions: List[Decimal] = Field(..., description="Daily predictions")
    confidence_intervals: List[Tuple[Decimal, Decimal]] = Field(
        ..., description="(lower, upper) confidence bounds"
    )
    forecast_dates: List[date_type]
    model_params: Dict[str, int] = Field(..., description="ARIMA (p, d, q) parameters")
    accuracy_score: Optional[float] = Field(None, description="Model accuracy percentage")


class AllForecastsResponse(BaseModel):
    """Schema for all categories forecast response."""

    forecasts: Dict[str, ForecastResponse] = Field(..., description="Forecasts by category")
    total_categories: int = Field(..., description="Total number of categories forecasted")


class AnomalyResponse(BaseModel):
    """Schema for spending anomaly response."""

    date: date_type
    category: str
    amount: Decimal
    expected_amount: Decimal
    deviation_percent: float
    severity: str = Field(..., description="LOW, MEDIUM, or HIGH")
