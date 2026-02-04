"""Budget service for managing budgets and tracking spending."""

from datetime import datetime, date as date_type
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID
from dataclasses import dataclass

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.budget import Budget
from app.models.transaction import Transaction
from app.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class BudgetProgress:
    """Budget progress for a category."""

    category: str
    allocated: Decimal
    spent: Decimal
    remaining: Decimal
    percent_used: float
    status: str  # ON_TRACK, WARNING, EXCEEDED


@dataclass
class BudgetAlert:
    """Budget alert for overspending."""

    category: str
    allocated: Decimal
    spent: Decimal
    percent_over: float
    severity: str  # WARNING (>80%), CRITICAL (>100%)
    message: str


class BudgetService:
    """Service for managing budgets and tracking spending."""

    def __init__(self, db: AsyncSession):
        """Initialize budget service.

        Args:
            db: Database session
        """
        self.db = db

    async def create_budget(
        self,
        user_id: UUID,
        name: str,
        period_start: date_type,
        period_end: date_type,
        allocations: Dict[str, Decimal],
    ) -> Budget:
        """Create a new budget.

        Args:
            user_id: User ID
            name: Budget name
            period_start: Budget period start date
            period_end: Budget period end date
            allocations: Dictionary mapping category to allocated amount

        Returns:
            Created budget

        Raises:
            ValueError: If period_end is before period_start
        """
        if period_end < period_start:
            raise ValueError("Budget period end must be after start")

        # Convert Decimal values to float for JSON storage
        allocations_json = {category: float(amount) for category, amount in allocations.items()}

        budget = Budget(
            user_id=user_id,
            name=name,
            period_start=period_start,
            period_end=period_end,
            allocations=allocations_json,
        )

        self.db.add(budget)
        await self.db.flush()
        await self.db.refresh(budget)

        logger.info(
            "Budget created",
            budget_id=str(budget.id),
            user_id=str(user_id),
            name=name,
            period_start=str(period_start),
            period_end=str(period_end),
            total_allocated=sum(allocations.values()),
        )

        return budget

    async def get_budget(self, budget_id: UUID, user_id: UUID) -> Optional[Budget]:
        """Get a budget by ID.

        Args:
            budget_id: Budget ID
            user_id: User ID (for authorization)

        Returns:
            Budget if found and belongs to user, None otherwise
        """
        stmt = select(Budget).where(and_(Budget.id == budget_id, Budget.user_id == user_id))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_budgets(self, user_id: UUID, active_only: bool = False) -> List[Budget]:
        """List all budgets for a user.

        Args:
            user_id: User ID
            active_only: If True, only return budgets that include current date

        Returns:
            List of budgets
        """
        stmt = select(Budget).where(Budget.user_id == user_id)

        if active_only:
            today = datetime.utcnow().date()
            stmt = stmt.where(and_(Budget.period_start <= today, Budget.period_end >= today))

        stmt = stmt.order_by(Budget.period_start.desc())

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_budget_progress(
        self, user_id: UUID, budget_id: UUID
    ) -> Dict[str, BudgetProgress]:
        """Get budget progress for all categories.

        Args:
            user_id: User ID
            budget_id: Budget ID

        Returns:
            Dictionary mapping category to BudgetProgress
        """
        # Get budget
        budget = await self.get_budget(budget_id, user_id)
        if not budget:
            return {}

        # Get actual spending for each category
        stmt = (
            select(Transaction.category, func.sum(Transaction.amount).label("total_spent"))
            .where(
                and_(
                    Transaction.user_id == user_id,
                    Transaction.type == "EXPENSE",
                    Transaction.date >= budget.period_start,
                    Transaction.date <= budget.period_end,
                    Transaction.deleted_at.is_(None),
                )
            )
            .group_by(Transaction.category)
        )

        result = await self.db.execute(stmt)
        spending = {row.category: Decimal(str(row.total_spent)) for row in result.all()}

        # Calculate progress for each category
        progress = {}
        for category, allocated_float in budget.allocations.items():
            allocated = Decimal(str(allocated_float))
            spent = spending.get(category, Decimal(0))
            remaining = allocated - spent
            percent_used = float((spent / allocated) * 100) if allocated > 0 else 0

            # Determine status
            if percent_used >= 100:
                status = "EXCEEDED"
            elif percent_used >= 80:
                status = "WARNING"
            else:
                status = "ON_TRACK"

            progress[category] = BudgetProgress(
                category=category,
                allocated=allocated,
                spent=spent,
                remaining=remaining,
                percent_used=percent_used,
                status=status,
            )

        logger.debug(
            "Budget progress calculated",
            budget_id=str(budget_id),
            user_id=str(user_id),
            categories=len(progress),
        )

        return progress

    async def check_budget_alerts(self, user_id: UUID, budget_id: UUID) -> List[BudgetAlert]:
        """Check for budget alerts (overspending warnings).

        Args:
            user_id: User ID
            budget_id: Budget ID

        Returns:
            List of budget alerts
        """
        progress = await self.get_budget_progress(user_id, budget_id)

        alerts = []
        for category, prog in progress.items():
            # Generate alert if spending exceeds 80% of budget
            if prog.percent_used >= 80:
                percent_over = prog.percent_used - 100

                if prog.percent_used >= 100:
                    severity = "CRITICAL"
                    message = (
                        f"Budget exceeded for {category}! "
                        f"Spent ${prog.spent:.2f} of ${prog.allocated:.2f} "
                        f"({percent_over:+.1f}% over budget)"
                    )
                else:
                    severity = "WARNING"
                    message = (
                        f"Approaching budget limit for {category}. "
                        f"Spent ${prog.spent:.2f} of ${prog.allocated:.2f} "
                        f"({prog.percent_used:.1f}% used)"
                    )

                alerts.append(
                    BudgetAlert(
                        category=category,
                        allocated=prog.allocated,
                        spent=prog.spent,
                        percent_over=percent_over,
                        severity=severity,
                        message=message,
                    )
                )

        if alerts:
            logger.warning(
                "Budget alerts generated",
                budget_id=str(budget_id),
                user_id=str(user_id),
                alert_count=len(alerts),
            )

        return alerts

    async def update_budget(
        self,
        budget_id: UUID,
        user_id: UUID,
        name: Optional[str] = None,
        allocations: Optional[Dict[str, Decimal]] = None,
    ) -> Optional[Budget]:
        """Update a budget.

        Args:
            budget_id: Budget ID
            user_id: User ID (for authorization)
            name: New budget name (optional)
            allocations: New allocations (optional)

        Returns:
            Updated budget if found, None otherwise
        """
        budget = await self.get_budget(budget_id, user_id)
        if not budget:
            return None

        if name is not None:
            budget.name = name

        if allocations is not None:
            budget.allocations = {
                category: float(amount) for category, amount in allocations.items()
            }

        budget.updated_at = datetime.utcnow()
        await self.db.flush()
        await self.db.refresh(budget)

        logger.info("Budget updated", budget_id=str(budget_id), user_id=str(user_id))

        return budget

    async def delete_budget(self, budget_id: UUID, user_id: UUID) -> bool:
        """Delete a budget.

        Args:
            budget_id: Budget ID
            user_id: User ID (for authorization)

        Returns:
            True if deleted, False if not found
        """
        budget = await self.get_budget(budget_id, user_id)
        if not budget:
            return False

        await self.db.delete(budget)
        await self.db.flush()

        logger.info("Budget deleted", budget_id=str(budget_id), user_id=str(user_id))

        return True
