"""Budget API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.budget import (
    BudgetCreate,
    BudgetUpdate,
    BudgetResponse,
    BudgetProgressResponse,
    BudgetAlertResponse,
    BudgetSuggestionResponse,
    ApplyOptimizationRequest,
)
from app.services.budget_service import BudgetService
from app.services.budget_optimizer import BudgetOptimizer, BudgetSuggestion

router = APIRouter()


# Response Models
class BudgetProgressListResponse(BaseModel):
    """Budget progress list response."""

    progress: dict[str, BudgetProgressResponse]
    alerts: list[BudgetAlertResponse]


class BudgetOptimizationResponse(BaseModel):
    """Budget optimization response."""

    suggestions: list[BudgetSuggestionResponse]


# Dependencies
async def get_budget_service(db: AsyncSession = Depends(get_db)) -> BudgetService:
    """Get budget service instance."""
    return BudgetService(db)


async def get_budget_optimizer(db: AsyncSession = Depends(get_db)) -> BudgetOptimizer:
    """Get budget optimizer instance."""
    return BudgetOptimizer(db)


# Endpoints
@router.post("", response_model=BudgetResponse, status_code=201)
async def create_budget(
    budget: BudgetCreate,
    user_id: UUID = Query(..., description="User ID"),
    service: BudgetService = Depends(get_budget_service),
) -> BudgetResponse:
    """Create a new budget.

    Args:
        budget: Budget data
        user_id: User ID
        service: Budget service

    Returns:
        Created budget

    Raises:
        HTTPException: If creation fails
    """
    try:
        created = await service.create_budget(
            user_id=user_id,
            name=budget.name,
            period_start=budget.period_start,
            period_end=budget.period_end,
            allocations=budget.allocations,
        )
        return BudgetResponse.model_validate(created)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create budget: {str(e)}")


@router.get("", response_model=list[BudgetResponse])
async def list_budgets(
    user_id: UUID = Query(..., description="User ID"),
    active_only: bool = Query(False, description="Only return active budgets"),
    service: BudgetService = Depends(get_budget_service),
) -> list[BudgetResponse]:
    """List all budgets for a user.

    Args:
        user_id: User ID
        active_only: If True, only return budgets that include current date
        service: Budget service

    Returns:
        List of budgets
    """
    try:
        budgets = await service.list_budgets(user_id, active_only)
        return [BudgetResponse.model_validate(b) for b in budgets]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list budgets: {str(e)}")


@router.get("/{budget_id}", response_model=BudgetResponse)
async def get_budget(
    budget_id: UUID,
    user_id: UUID = Query(..., description="User ID"),
    service: BudgetService = Depends(get_budget_service),
) -> BudgetResponse:
    """Get a single budget by ID.

    Args:
        budget_id: Budget ID
        user_id: User ID
        service: Budget service

    Returns:
        Budget details

    Raises:
        HTTPException: If budget not found
    """
    try:
        budget = await service.get_budget(budget_id, user_id)
        if not budget:
            raise HTTPException(status_code=404, detail=f"Budget {budget_id} not found")
        return BudgetResponse.model_validate(budget)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get budget: {str(e)}")


@router.get("/{budget_id}/progress", response_model=BudgetProgressListResponse)
async def get_budget_progress(
    budget_id: UUID,
    user_id: UUID = Query(..., description="User ID"),
    service: BudgetService = Depends(get_budget_service),
) -> BudgetProgressListResponse:
    """Get budget progress for all categories.

    Args:
        budget_id: Budget ID
        user_id: User ID
        service: Budget service

    Returns:
        Budget progress and alerts

    Raises:
        HTTPException: If budget not found
    """
    try:
        # Get progress
        progress_dict = await service.get_budget_progress(user_id, budget_id)
        if not progress_dict:
            raise HTTPException(status_code=404, detail=f"Budget {budget_id} not found")

        # Get alerts
        alerts = await service.check_budget_alerts(user_id, budget_id)

        # Convert to response format
        progress_response = {
            category: BudgetProgressResponse(
                category=prog.category,
                allocated=prog.allocated,
                spent=prog.spent,
                remaining=prog.remaining,
                percent_used=prog.percent_used,
                status=prog.status,
            )
            for category, prog in progress_dict.items()
        }

        alerts_response = [
            BudgetAlertResponse(
                category=alert.category,
                allocated=alert.allocated,
                spent=alert.spent,
                percent_over=alert.percent_over,
                severity=alert.severity,
                message=alert.message,
            )
            for alert in alerts
        ]

        return BudgetProgressListResponse(progress=progress_response, alerts=alerts_response)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get budget progress: {str(e)}")


@router.post("/{budget_id}/optimize", response_model=BudgetOptimizationResponse)
async def get_optimization_suggestions(
    budget_id: UUID,
    user_id: UUID = Query(..., description="User ID"),
    historical_months: int = Query(3, ge=1, le=12, description="Months of history to analyze"),
    budget_service: BudgetService = Depends(get_budget_service),
    optimizer: BudgetOptimizer = Depends(get_budget_optimizer),
) -> BudgetOptimizationResponse:
    """Get budget optimization suggestions.

    Args:
        budget_id: Budget ID
        user_id: User ID
        historical_months: Number of months to analyze
        budget_service: Budget service
        optimizer: Budget optimizer

    Returns:
        Budget optimization suggestions

    Raises:
        HTTPException: If budget not found
    """
    try:
        # Get budget
        budget = await budget_service.get_budget(budget_id, user_id)
        if not budget:
            raise HTTPException(status_code=404, detail=f"Budget {budget_id} not found")

        # Get suggestions
        suggestions = await optimizer.suggest_optimizations(
            user_id=user_id, budget=budget, historical_months=historical_months
        )

        # Convert to response format
        suggestions_response = [
            BudgetSuggestionResponse(
                category=s.category,
                current_allocation=s.current_allocation,
                suggested_allocation=s.suggested_allocation,
                change_amount=s.change_amount,
                change_percent=s.change_percent,
                reason=s.reason,
                priority=s.priority,
            )
            for s in suggestions
        ]

        return BudgetOptimizationResponse(suggestions=suggestions_response)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get optimization suggestions: {str(e)}"
        )


@router.put("/{budget_id}/apply-optimization", response_model=BudgetResponse)
async def apply_optimization(
    budget_id: UUID,
    request: ApplyOptimizationRequest,
    user_id: UUID = Query(..., description="User ID"),
    budget_service: BudgetService = Depends(get_budget_service),
    optimizer: BudgetOptimizer = Depends(get_budget_optimizer),
) -> BudgetResponse:
    """Apply budget optimization suggestions.

    Args:
        budget_id: Budget ID
        request: Optimization request with suggestions and approval
        user_id: User ID
        budget_service: Budget service
        optimizer: Budget optimizer

    Returns:
        Updated budget

    Raises:
        HTTPException: If budget not found or user has not approved
    """
    try:
        # Convert response format back to service format
        suggestions = [
            BudgetSuggestion(
                category=s.category,
                current_allocation=s.current_allocation,
                suggested_allocation=s.suggested_allocation,
                change_amount=s.change_amount,
                change_percent=s.change_percent,
                reason=s.reason,
                priority=s.priority,
            )
            for s in request.suggestions
        ]

        # Apply optimization
        updated = await optimizer.apply_optimization(
            budget_id=budget_id,
            user_id=user_id,
            suggestions=suggestions,
            user_approved=request.user_approved,
        )

        if not updated:
            raise HTTPException(status_code=404, detail=f"Budget {budget_id} not found")

        return BudgetResponse.model_validate(updated)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to apply optimization: {str(e)}")


@router.put("/{budget_id}", response_model=BudgetResponse)
async def update_budget(
    budget_id: UUID,
    updates: BudgetUpdate,
    user_id: UUID = Query(..., description="User ID"),
    service: BudgetService = Depends(get_budget_service),
) -> BudgetResponse:
    """Update a budget.

    Args:
        budget_id: Budget ID
        updates: Budget updates
        user_id: User ID
        service: Budget service

    Returns:
        Updated budget

    Raises:
        HTTPException: If budget not found or update fails
    """
    try:
        # Check if any updates provided
        update_dict = updates.model_dump(exclude_unset=True)

        if not update_dict:
            raise HTTPException(status_code=400, detail="No updates provided")

        updated = await service.update_budget(
            budget_id=budget_id, user_id=user_id, name=updates.name, allocations=updates.allocations
        )

        if not updated:
            raise HTTPException(status_code=404, detail=f"Budget {budget_id} not found")

        return BudgetResponse.model_validate(updated)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update budget: {str(e)}")


@router.delete("/{budget_id}", status_code=204)
async def delete_budget(
    budget_id: UUID,
    user_id: UUID = Query(..., description="User ID"),
    service: BudgetService = Depends(get_budget_service),
) -> None:
    """Delete a budget.

    Args:
        budget_id: Budget ID
        user_id: User ID
        service: Budget service

    Raises:
        HTTPException: If budget not found or deletion fails
    """
    try:
        success = await service.delete_budget(budget_id, user_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Budget {budget_id} not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete budget: {str(e)}")
