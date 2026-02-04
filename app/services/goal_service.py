"""Goal service for managing financial goals and tracking progress."""

from datetime import datetime, timedelta
from datetime import date as date_type
from decimal import Decimal
from typing import List, Optional
from uuid import UUID
from dataclasses import dataclass

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.financial_goal import FinancialGoal
from app.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class GoalProgress:
    """Goal progress information."""

    goal_id: UUID
    name: str
    target_amount: Decimal
    current_amount: Decimal
    progress_percent: float
    remaining_amount: Decimal
    days_remaining: Optional[int]
    estimated_completion_date: Optional[date_type]
    is_at_risk: bool
    risk_reason: Optional[str]


@dataclass
class GoalRiskAlert:
    """Goal risk alert."""

    goal_id: UUID
    name: str
    severity: str  # WARNING, CRITICAL
    message: str
    recommended_action: str


class GoalService:
    """Service for managing financial goals and tracking progress."""

    def __init__(self, db: AsyncSession):
        """Initialize goal service.

        Args:
            db: Database session
        """
        self.db = db

    async def create_goal(
        self,
        user_id: UUID,
        name: str,
        target_amount: Decimal,
        deadline: Optional[date_type] = None,
        category: Optional[str] = None,
        initial_amount: Decimal = Decimal(0),
    ) -> FinancialGoal:
        """Create a new financial goal.

        Args:
            user_id: User ID
            name: Goal name
            target_amount: Target amount to achieve
            deadline: Optional deadline date
            category: Optional category to link with transactions
            initial_amount: Initial amount (default: 0)

        Returns:
            Created goal

        Raises:
            ValueError: If target_amount is not positive
        """
        if target_amount <= 0:
            raise ValueError("Target amount must be positive")

        if initial_amount < 0:
            raise ValueError("Initial amount cannot be negative")

        goal = FinancialGoal(
            user_id=user_id,
            name=name,
            target_amount=target_amount,
            current_amount=initial_amount,
            deadline=deadline,
            category=category,
            status="ACTIVE",
        )

        self.db.add(goal)
        await self.db.flush()
        await self.db.refresh(goal)

        logger.info(
            "Financial goal created",
            goal_id=str(goal.id),
            user_id=str(user_id),
            name=name,
            target_amount=str(target_amount),
            deadline=str(deadline) if deadline else None,
        )

        return goal

    async def get_goal(self, goal_id: UUID, user_id: UUID) -> Optional[FinancialGoal]:
        """Get a goal by ID.

        Args:
            goal_id: Goal ID
            user_id: User ID (for authorization)

        Returns:
            Goal if found and belongs to user, None otherwise
        """
        stmt = select(FinancialGoal).where(
            and_(FinancialGoal.id == goal_id, FinancialGoal.user_id == user_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_goals(self, user_id: UUID, status: Optional[str] = None) -> List[FinancialGoal]:
        """List all goals for a user.

        Args:
            user_id: User ID
            status: Optional status filter (ACTIVE, ACHIEVED, ARCHIVED)

        Returns:
            List of goals
        """
        stmt = select(FinancialGoal).where(FinancialGoal.user_id == user_id)

        if status:
            stmt = stmt.where(FinancialGoal.status == status)

        stmt = stmt.order_by(FinancialGoal.created_at.desc())

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_goal_progress(self, user_id: UUID, goal_id: UUID) -> Optional[GoalProgress]:
        """Get detailed progress information for a goal.

        Args:
            user_id: User ID
            goal_id: Goal ID

        Returns:
            GoalProgress if goal found, None otherwise
        """
        goal = await self.get_goal(goal_id, user_id)
        if not goal:
            return None

        # Calculate progress percentage
        progress_percent = (
            float((goal.current_amount / goal.target_amount) * 100) if goal.target_amount > 0 else 0
        )
        remaining_amount = goal.target_amount - goal.current_amount

        # Calculate days remaining
        days_remaining = None
        if goal.deadline:
            today = datetime.utcnow().date()
            days_remaining = (goal.deadline - today).days

        # Estimate completion date based on progress rate
        estimated_completion_date = None
        is_at_risk = False
        risk_reason = None

        if goal.deadline and goal.current_amount > 0:
            # Calculate progress rate (amount per day)
            days_since_creation = (datetime.utcnow().date() - goal.created_at.date()).days
            if days_since_creation > 0:
                daily_rate = goal.current_amount / days_since_creation

                if daily_rate > 0:
                    days_to_completion = int(remaining_amount / daily_rate)
                    estimated_completion_date = datetime.utcnow().date() + timedelta(
                        days=days_to_completion
                    )

                    # Check if at risk
                    if estimated_completion_date > goal.deadline:
                        is_at_risk = True
                        days_behind = (estimated_completion_date - goal.deadline).days
                        risk_reason = (
                            f"Projected to miss deadline by {days_behind} days at current rate"
                        )

        return GoalProgress(
            goal_id=goal.id,
            name=goal.name,
            target_amount=goal.target_amount,
            current_amount=goal.current_amount,
            progress_percent=progress_percent,
            remaining_amount=remaining_amount,
            days_remaining=days_remaining,
            estimated_completion_date=estimated_completion_date,
            is_at_risk=is_at_risk,
            risk_reason=risk_reason,
        )

    async def update_goal_progress(
        self, goal_id: UUID, user_id: UUID, amount: Decimal
    ) -> Optional[FinancialGoal]:
        """Update goal progress by adding an amount.

        This method is typically called automatically when a transaction
        matching the goal's category is created.

        Args:
            goal_id: Goal ID
            user_id: User ID
            amount: Amount to add to current progress

        Returns:
            Updated goal if found, None otherwise
        """
        goal = await self.get_goal(goal_id, user_id)
        if not goal:
            return None

        # Update current amount
        goal.current_amount += amount
        goal.updated_at = datetime.utcnow()

        # Check if goal is achieved
        if goal.current_amount >= goal.target_amount and goal.status == "ACTIVE":
            goal.status = "ACHIEVED"
            logger.info(
                "Financial goal achieved!",
                goal_id=str(goal_id),
                user_id=str(user_id),
                name=goal.name,
                final_amount=str(goal.current_amount),
            )

        await self.db.flush()
        await self.db.refresh(goal)

        logger.debug(
            "Goal progress updated",
            goal_id=str(goal_id),
            user_id=str(user_id),
            amount_added=str(amount),
            new_total=str(goal.current_amount),
        )

        return goal

    async def update_goal_progress_from_transaction(
        self, user_id: UUID, transaction_amount: Decimal, transaction_category: str
    ) -> List[FinancialGoal]:
        """Update progress for all goals matching transaction category.

        This method is called automatically when a transaction is created.

        Args:
            user_id: User ID
            transaction_amount: Transaction amount
            transaction_category: Transaction category

        Returns:
            List of updated goals
        """
        # Find active goals matching the category
        stmt = select(FinancialGoal).where(
            and_(
                FinancialGoal.user_id == user_id,
                FinancialGoal.category == transaction_category,
                FinancialGoal.status == "ACTIVE",
            )
        )

        result = await self.db.execute(stmt)
        goals = list(result.scalars().all())

        updated_goals = []
        for goal in goals:
            updated_goal = await self.update_goal_progress(goal.id, user_id, transaction_amount)
            if updated_goal:
                updated_goals.append(updated_goal)

        if updated_goals:
            logger.info(
                "Goals auto-updated from transaction",
                user_id=str(user_id),
                category=transaction_category,
                amount=str(transaction_amount),
                goals_updated=len(updated_goals),
            )

        return updated_goals

    async def check_goal_risks(self, user_id: UUID) -> List[GoalRiskAlert]:
        """Check all active goals for risk alerts.

        Args:
            user_id: User ID

        Returns:
            List of risk alerts
        """
        # Get all active goals
        goals = await self.list_goals(user_id, status="ACTIVE")

        alerts = []
        for goal in goals:
            progress = await self.get_goal_progress(user_id, goal.id)

            if progress and progress.is_at_risk:
                # Determine severity
                if progress.days_remaining and progress.days_remaining < 30:
                    severity = "CRITICAL"
                    recommended_action = f"Increase contributions significantly to meet deadline in {progress.days_remaining} days"
                else:
                    severity = "WARNING"
                    recommended_action = (
                        "Consider increasing your contribution rate to stay on track"
                    )

                alerts.append(
                    GoalRiskAlert(
                        goal_id=goal.id,
                        name=goal.name,
                        severity=severity,
                        message=progress.risk_reason or "Goal at risk of not being met",
                        recommended_action=recommended_action,
                    )
                )

        if alerts:
            logger.warning(
                "Goal risk alerts generated", user_id=str(user_id), alert_count=len(alerts)
            )

        return alerts

    async def update_goal(
        self,
        goal_id: UUID,
        user_id: UUID,
        name: Optional[str] = None,
        target_amount: Optional[Decimal] = None,
        deadline: Optional[date_type] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Optional[FinancialGoal]:
        """Update a goal.

        Args:
            goal_id: Goal ID
            user_id: User ID (for authorization)
            name: New name (optional)
            target_amount: New target amount (optional)
            deadline: New deadline (optional)
            category: New category (optional)
            status: New status (optional)

        Returns:
            Updated goal if found, None otherwise
        """
        goal = await self.get_goal(goal_id, user_id)
        if not goal:
            return None

        if name is not None:
            goal.name = name

        if target_amount is not None:
            if target_amount <= 0:
                raise ValueError("Target amount must be positive")
            goal.target_amount = target_amount

        if deadline is not None:
            goal.deadline = deadline

        if category is not None:
            goal.category = category

        if status is not None:
            if status not in ["ACTIVE", "ACHIEVED", "ARCHIVED"]:
                raise ValueError("Invalid status")
            goal.status = status

        goal.updated_at = datetime.utcnow()
        await self.db.flush()
        await self.db.refresh(goal)

        logger.info("Goal updated", goal_id=str(goal_id), user_id=str(user_id))

        return goal

    async def delete_goal(self, goal_id: UUID, user_id: UUID) -> bool:
        """Delete a goal.

        Args:
            goal_id: Goal ID
            user_id: User ID (for authorization)

        Returns:
            True if deleted, False if not found
        """
        goal = await self.get_goal(goal_id, user_id)
        if not goal:
            return False

        await self.db.delete(goal)
        await self.db.flush()

        logger.info("Goal deleted", goal_id=str(goal_id), user_id=str(user_id))

        return True
