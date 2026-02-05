"""Prediction API endpoints."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user_id
from app.schemas.prediction import ForecastResponse, AllForecastsResponse, AnomalyResponse
from app.ml.prediction_engine import PredictionEngine

logger = logging.getLogger(__name__)
router = APIRouter()

# Default categories for validation (until Phase 2 constants)
VALID_CATEGORIES = [
    "Food & Dining",
    "Shopping & Retail",
    "Transportation",
    "Entertainment",
    "Utilities",
    "Healthcare",
    "Travel",
    "Subscriptions",
    "Income",
    "Transfer",
    "Other Expenses",
]

# Dependencies
async def get_prediction_engine(db: AsyncSession = Depends(get_db)) -> PredictionEngine:
    """Get prediction engine instance."""
    return PredictionEngine(db)


# Endpoints
@router.get("/forecast", response_model=AllForecastsResponse)
async def get_expense_forecasts(
    user_id: UUID = Depends(get_current_user_id),
    periods: int = Query(30, ge=1, le=90, description="Number of days to forecast"),
    lookback_days: int = Query(90, ge=30, le=365, description="Historical days to use"),
    engine: PredictionEngine = Depends(get_prediction_engine),
) -> AllForecastsResponse:
    """Get expense forecasts for all categories.

    Args:
        user_id: User ID
        periods: Number of days to forecast (1-90)
        lookback_days: Historical days to use (30-365)
        engine: Prediction engine

    Returns:
        Forecasts for all categories with sufficient data
    """
    try:
        forecasts_dict = await engine.forecast_all_categories(
            user_id=user_id, periods=periods, lookback_days=lookback_days
        )

        # Convert to response format
        forecasts_response = {
            category: ForecastResponse(
                category=forecast.category,
                predictions=forecast.predictions,
                confidence_intervals=forecast.confidence_intervals,
                forecast_dates=forecast.forecast_dates,
                model_params=forecast.model_params,
                accuracy_score=forecast.accuracy_score,
            )
            for category, forecast in forecasts_dict.items()
        }

        return AllForecastsResponse(
            forecasts=forecasts_response, total_categories=len(forecasts_response)
        )
    except Exception as e:
        logger.error(f"Failed to generate forecasts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred. Please try again later.")


@router.get("/forecast/{category}", response_model=ForecastResponse)
async def get_category_forecast(
    category: str,
    user_id: UUID = Depends(get_current_user_id),
    periods: int = Query(30, ge=1, le=90, description="Number of days to forecast"),
    lookback_days: int = Query(90, ge=30, le=365, description="Historical days to use"),
    engine: PredictionEngine = Depends(get_prediction_engine),
) -> ForecastResponse:
    """Get expense forecast for a specific category.

    Args:
        category: Expense category
        user_id: User ID
        periods: Number of days to forecast (1-90)
        lookback_days: Historical days to use (30-365)
        engine: Prediction engine

    Returns:
        Forecast for the specified category

    Raises:
        HTTPException: If insufficient data or forecast fails
    """
    if category not in VALID_CATEGORIES:
        # Check if it might be a custom category or allow it if not in list but logs warning?
        # For now, we enforce valid categories to match requirement
        # "Add category validation — check category param against VALID_CATEGORIES"
        # However, users might have custom categories.
        # But based on the instruction "Add an enum or a list check", strict check seems implied.
        pass # Actually, let's just warn or allow flexibility if needed?
             # The instruction is explicit: "if category not in VALID_CATEGORIES: raise HTTPException"

    if category not in VALID_CATEGORIES:
         raise HTTPException(status_code=400, detail=f"Unknown category: {category}")

    try:
        forecast = await engine.forecast_expenses(
            user_id=user_id, category=category, periods=periods, lookback_days=lookback_days
        )

        if not forecast:
            raise HTTPException(
                status_code=404,
                detail=f"Insufficient data to forecast {category}. Need at least 30 days of transactions.",
            )

        return ForecastResponse(
            category=forecast.category,
            predictions=forecast.predictions,
            confidence_intervals=forecast.confidence_intervals,
            forecast_dates=forecast.forecast_dates,
            model_params=forecast.model_params,
            accuracy_score=forecast.accuracy_score,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate forecast: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred. Please try again later.")


@router.get("/anomalies/{category}", response_model=list[AnomalyResponse])
async def get_spending_anomalies(
    category: str,
    user_id: UUID = Depends(get_current_user_id),
    lookback_days: int = Query(90, ge=30, le=365, description="Days to analyze"),
    threshold_percent: float = Query(50.0, ge=10, le=200, description="Deviation threshold"),
    engine: PredictionEngine = Depends(get_prediction_engine),
) -> list[AnomalyResponse]:
    """Detect unusual spending patterns in a category.

    Args:
        category: Expense category
        user_id: User ID
        lookback_days: Days to analyze (30-365)
        threshold_percent: Deviation threshold (10-200%)
        engine: Prediction engine

    Returns:
        List of detected anomalies
    """
    if category not in VALID_CATEGORIES:
         raise HTTPException(status_code=400, detail=f"Unknown category: {category}")

    try:
        anomalies = await engine.detect_anomalies(
            user_id=user_id,
            category=category,
            lookback_days=lookback_days,
            threshold_percent=threshold_percent,
        )

        return [
            AnomalyResponse(
                date=anomaly.date,
                category=anomaly.category,
                amount=anomaly.amount,
                expected_amount=anomaly.expected_amount,
                deviation_percent=anomaly.deviation_percent,
                severity=anomaly.severity,
            )
            for anomaly in anomalies
        ]
    except Exception as e:
        logger.error(f"Failed to detect anomalies: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred. Please try again later.")
