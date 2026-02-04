"""Goal API endpoints."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.goal import (
    GoalCreate,
    GoalUpdate,
    GoalProgressUpdate,
    GoalResponse,
    GoalProgressResponse,
    GoalRiskAlertResponse
)
from app.services.goal_service import GoalService

router = APIRouter()


# Dependencies
async def get_goal_service(db: AsyncSession = Depends(get_db)) -> GoalService:
    """Get goal service instance."""
    return GoalService(db)


# Endpoints
@router.post("", response_model=GoalResponse, status_code=201)
async def create_goal(
    goal: GoalCreate,
    user_id: UUID = Query(..., description="User ID"),
    service: GoalService = Depends(get_goal_service)
) -> GoalResponse:
    """Create a new financial goal.
    
    Args:
        goal: Goal data
        user_id: User ID
        service: Goal service
        
    Returns:
        Created goal
        
    Raises:
        HTTPException: If creation fails
    """
    try:
        created = await service.create_goal(
            user_id=user_id,
            name=goal.name,
            target_amount=goal.target_amount,
            deadline=goal.deadline,
            category=goal.category,
            initial_amount=goal.initial_amount
        )
        return GoalResponse.model_validate(created)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create goal: {str(e)}")


@router.get("", response_model=list[GoalResponse])
async def list_goals(
    user_id: UUID = Query(..., description="User ID"),
    status: Optional[str] = Query(None, description="Filter by status (ACTIVE, ACHIEVED, ARCHIVED)"),
    service: GoalService = Depends(get_goal_service)
) -> list[GoalResponse]:
    """List all goals for a user.
    
    Args:
        user_id: User ID
        status: Optional status filter
        service: Goal service
        
    Returns:
        List of goals
    """
    try:
        goals = await service.list_goals(user_id, status)
        return [GoalResponse.model_validate(g) for g in goals]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list goals: {str(e)}")


@router.get("/{goal_id}", response_model=GoalResponse)
async def get_goal(
    goal_id: UUID,
    user_id: UUID = Query(..., description="User ID"),
    service: GoalService = Depends(get_goal_service)
) -> GoalResponse:
    """Get a single goal by ID.
    
    Args:
        goal_id: Goal ID
        user_id: User ID
        service: Goal service
        
    Returns:
        Goal details
        
    Raises:
        HTTPException: If goal not found
    """
    try:
        goal = await service.get_goal(goal_id, user_id)
        if not goal:
            raise HTTPException(status_code=404, detail=f"Goal {goal_id} not found")
        return GoalResponse.model_validate(goal)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get goal: {str(e)}")


@router.get("/{goal_id}/progress", response_model=GoalProgressResponse)
async def get_goal_progress(
    goal_id: UUID,
    user_id: UUID = Query(..., description="User ID"),
    service: GoalService = Depends(get_goal_service)
) -> GoalProgressResponse:
    """Get detailed progress information for a goal.
    
    Args:
        goal_id: Goal ID
        user_id: User ID
        service: Goal service
        
    Returns:
        Goal progress details
        
    Raises:
        HTTPException: If goal not found
    """
    try:
        progress = await service.get_goal_progress(user_id, goal_id)
        if not progress:
            raise HTTPException(status_code=404, detail=f"Goal {goal_id} not found")
        
        return GoalProgressResponse(
            goal_id=progress.goal_id,
            name=progress.name,
            target_amount=progress.target_amount,
            current_amount=progress.current_amount,
            progress_percent=progress.progress_percent,
            remaining_amount=progress.remaining_amount,
            days_remaining=progress.days_remaining,
            estimated_completion_date=progress.estimated_completion_date,
            is_at_risk=progress.is_at_risk,
            risk_reason=progress.risk_reason
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get goal progress: {str(e)}")


@router.post("/{goal_id}/progress", response_model=GoalResponse)
async def update_goal_progress(
    goal_id: UUID,
    progress_update: GoalProgressUpdate,
    user_id: UUID = Query(..., description="User ID"),
    service: GoalService = Depends(get_goal_service)
) -> GoalResponse:
    """Update goal progress by adding an amount.
    
    Args:
        goal_id: Goal ID
        progress_update: Progress update data
        user_id: User ID
        service: Goal service
        
    Returns:
        Updated goal
        
    Raises:
        HTTPException: If goal not found
    """
    try:
        updated = await service.update_goal_progress(
            goal_id=goal_id,
            user_id=user_id,
            amount=progress_update.amount
        )
        
        if not updated:
            raise HTTPException(status_code=404, detail=f"Goal {goal_id} not found")
        
        return GoalResponse.model_validate(updated)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update goal progress: {str(e)}")


@router.get("/risks/alerts", response_model=list[GoalRiskAlertResponse])
async def get_goal_risk_alerts(
    user_id: UUID = Query(..., description="User ID"),
    service: GoalService = Depends(get_goal_service)
) -> list[GoalRiskAlertResponse]:
    """Get risk alerts for all active goals.
    
    Args:
        user_id: User ID
        service: Goal service
        
    Returns:
        List of risk alerts
    """
    try:
        alerts = await service.check_goal_risks(user_id)
        
        return [
            GoalRiskAlertResponse(
                goal_id=alert.goal_id,
                name=alert.name,
                severity=alert.severity,
                message=alert.message,
                recommended_action=alert.recommended_action
            )
            for alert in alerts
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get risk alerts: {str(e)}")


@router.put("/{goal_id}", response_model=GoalResponse)
async def update_goal(
    goal_id: UUID,
    updates: GoalUpdate,
    user_id: UUID = Query(..., description="User ID"),
    service: GoalService = Depends(get_goal_service)
) -> GoalResponse:
    """Update a goal.
    
    Args:
        goal_id: Goal ID
        updates: Goal updates
        user_id: User ID
        service: Goal service
        
    Returns:
        Updated goal
        
    Raises:
        HTTPException: If goal not found or update fails
    """
    try:
        # Check if any updates provided
        update_dict = updates.model_dump(exclude_unset=True)
        
        if not update_dict:
            raise HTTPException(status_code=400, detail="No updates provided")
        
        updated = await service.update_goal(
            goal_id=goal_id,
            user_id=user_id,
            name=updates.name,
            target_amount=updates.target_amount,
            deadline=updates.deadline,
            category=updates.category,
            status=updates.status
        )
        
        if not updated:
            raise HTTPException(status_code=404, detail=f"Goal {goal_id} not found")
        
        return GoalResponse.model_validate(updated)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update goal: {str(e)}")


@router.delete("/{goal_id}", status_code=204)
async def delete_goal(
    goal_id: UUID,
    user_id: UUID = Query(..., description="User ID"),
    service: GoalService = Depends(get_goal_service)
) -> None:
    """Delete a goal.
    
    Args:
        goal_id: Goal ID
        user_id: User ID
        service: Goal service
        
    Raises:
        HTTPException: If goal not found or deletion fails
    """
    try:
        success = await service.delete_goal(goal_id, user_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Goal {goal_id} not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete goal: {str(e)}")
