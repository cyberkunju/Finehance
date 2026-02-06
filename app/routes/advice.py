"""Advice API endpoints."""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache import cache_manager
from app.database import get_db
from app.dependencies import get_current_user_id
from app.schemas.advice import AdviceResponse
from app.services.advice_generator import AdviceGenerator

logger = logging.getLogger(__name__)
router = APIRouter()

# Cache TTL for advice (5 minutes - advice doesn't change frequently)
ADVICE_CACHE_TTL = 300


# Dependencies
async def get_advice_generator(db: AsyncSession = Depends(get_db)) -> AdviceGenerator:
    """Get advice generator instance."""
    return AdviceGenerator(db)


# Endpoints
@router.get("", response_model=list[AdviceResponse])
async def get_personalized_advice(
    user_id: UUID = Depends(get_current_user_id),
    max_recommendations: int = Query(3, ge=1, le=10, description="Maximum recommendations"),
    generator: AdviceGenerator = Depends(get_advice_generator),
) -> list[AdviceResponse]:
    """Get personalized financial advice for dashboard.

    Args:
        user_id: User ID
        max_recommendations: Maximum number of recommendations (1-10)
        generator: Advice generator

    Returns:
        List of personalized advice, sorted by priority
    """
    # Try cache first
    cache_key = f"advice:{user_id}:{max_recommendations}"
    cached_advice = await cache_manager.get(cache_key)
    if cached_advice:
        return cached_advice

    try:
        advice_list = await generator.generate_dashboard_advice(
            user_id=user_id, max_recommendations=max_recommendations
        )

        result = [
            AdviceResponse(
                title=advice.title,
                message=advice.message,
                explanation=advice.explanation,
                priority=advice.priority.value,
                category=advice.category,
                action_items=advice.action_items,
                related_id=advice.related_id,
            )
            for advice in advice_list
        ]

        # Cache the result
        await cache_manager.set(cache_key, [r.model_dump() for r in result], ADVICE_CACHE_TTL)

        return result
    except Exception as e:
        logger.error(f"Failed to generate advice: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred. Please try again later.")


@router.get("/spending-alerts", response_model=list[AdviceResponse])
async def get_spending_alerts(
    user_id: UUID = Depends(get_current_user_id),
    budget_id: Optional[UUID] = Query(None, description="Optional specific budget ID"),
    generator: AdviceGenerator = Depends(get_advice_generator),
) -> list[AdviceResponse]:
    """Get spending alerts for budget overruns.

    Args:
        user_id: User ID
        budget_id: Optional specific budget ID to check
        generator: Advice generator

    Returns:
        List of spending alert advice
    """
    try:
        alerts = await generator.check_spending_alerts(user_id=user_id, budget_id=budget_id)

        return [
            AdviceResponse(
                title=advice.title,
                message=advice.message,
                explanation=advice.explanation,
                priority=advice.priority.value,
                category=advice.category,
                action_items=advice.action_items,
                related_id=advice.related_id,
            )
            for advice in alerts
        ]
    except Exception as e:
        logger.error(f"Failed to check spending alerts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred. Please try again later.")


@router.get("/savings-opportunities", response_model=list[AdviceResponse])
async def get_savings_opportunities(
    user_id: UUID = Depends(get_current_user_id),
    lookback_months: int = Query(3, ge=1, le=12, description="Months to analyze"),
    generator: AdviceGenerator = Depends(get_advice_generator),
) -> list[AdviceResponse]:
    """Get savings opportunity recommendations.

    Args:
        user_id: User ID
        lookback_months: Months to analyze (1-12)
        generator: Advice generator

    Returns:
        List of savings opportunity advice
    """
    try:
        opportunities = await generator.suggest_savings_opportunities(
            user_id=user_id, lookback_months=lookback_months
        )

        return [
            AdviceResponse(
                title=advice.title,
                message=advice.message,
                explanation=advice.explanation,
                priority=advice.priority.value,
                category=advice.category,
                action_items=advice.action_items,
                related_id=advice.related_id,
            )
            for advice in opportunities
        ]
    except Exception as e:
        logger.error(f"Failed to suggest savings opportunities: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred. Please try again later.")
