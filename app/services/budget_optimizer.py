"""Budget optimizer service for analyzing spending patterns and suggesting optimizations."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID
from dataclasses import dataclass

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Transaction
from app.models.budget import Budget
from app.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class SpendingPattern:
    """Spending pattern analysis for a category."""

    category: str
    average_spending: Decimal
    variance: Decimal
    min_spending: Decimal
    max_spending: Decimal
    transaction_count: int


@dataclass
class BudgetSuggestion:
    """Budget optimization suggestion."""

    category: str
    current_allocation: Decimal
    suggested_allocation: Decimal
    change_amount: Decimal
    change_percent: float
    reason: str
    priority: str  # HIGH, MEDIUM, LOW


class BudgetOptimizer:
    """Service for analyzing spending patterns and optimizing budgets."""

    def __init__(self, db: AsyncSession):
        """Initialize budget optimizer.

        Args:
            db: Database session
        """
        self.db = db

    async def analyze_spending_patterns(
        self, user_id: UUID, months: int = 3
    ) -> Dict[str, SpendingPattern]:
        """Analyze historical spending patterns.

        Args:
            user_id: User ID
            months: Number of months to analyze (default: 3)

        Returns:
            Dictionary mapping category to SpendingPattern
        """
        # Calculate date range
        end_date = datetime.now(timezone.utc).date()
        start_date = end_date - timedelta(days=months * 30)

        # Query spending by category
        stmt = (
            select(
                Transaction.category,
                func.avg(Transaction.amount).label("avg_amount"),
                func.stddev(Transaction.amount).label("variance"),
                func.min(Transaction.amount).label("min_amount"),
                func.max(Transaction.amount).label("max_amount"),
                func.count(Transaction.id).label("count"),
            )
            .where(
                and_(
                    Transaction.user_id == user_id,
                    Transaction.type == "EXPENSE",
                    Transaction.date >= start_date,
                    Transaction.date <= end_date,
                    Transaction.deleted_at.is_(None),
                )
            )
            .group_by(Transaction.category)
        )

        result = await self.db.execute(stmt)

        patterns = {}
        for row in result.all():
            patterns[row.category] = SpendingPattern(
                category=row.category,
                average_spending=Decimal(str(row.avg_amount or 0)),
                variance=Decimal(str(row.variance or 0)),
                min_spending=Decimal(str(row.min_amount or 0)),
                max_spending=Decimal(str(row.max_amount or 0)),
                transaction_count=row.count,
            )

        logger.info(
            "Spending patterns analyzed",
            user_id=str(user_id),
            months=months,
            categories=len(patterns),
        )

        return patterns

    async def suggest_optimizations(
        self, user_id: UUID, budget: Budget, historical_months: int = 3
    ) -> List[BudgetSuggestion]:
        """Suggest budget optimizations based on spending patterns.

        Analyzes historical spending and suggests reallocations:
        - Move funds from consistently underspent categories
        - Allocate to consistently overspent categories
        - Maintain total budget constraint

        Args:
            user_id: User ID
            budget: Current budget to optimize
            historical_months: Number of months to analyze (default: 3)

        Returns:
            List of budget suggestions
        """
        # Analyze spending patterns
        patterns = await self.analyze_spending_patterns(user_id, historical_months)

        # Calculate actual spending during budget period
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
        actual_spending = {row.category: Decimal(str(row.total_spent)) for row in result.all()}

        suggestions = []

        # Identify over/under spending categories
        for category, allocated_float in budget.allocations.items():
            allocated = Decimal(str(allocated_float))
            spent = actual_spending.get(category, Decimal(0))

            # Skip if no spending data
            if spent == 0:
                continue

            deviation_percent = (
                float(((spent - allocated) / allocated) * 100) if allocated > 0 else 0
            )

            # Consistent overspending (>15% deviation)
            if deviation_percent > 15:
                pattern = patterns.get(category)
                if pattern:
                    # Suggest increase based on actual spending with buffer
                    suggested = spent * Decimal("1.1")  # 10% buffer above actual
                    change = suggested - allocated

                    suggestions.append(
                        BudgetSuggestion(
                            category=category,
                            current_allocation=allocated,
                            suggested_allocation=suggested,
                            change_amount=change,
                            change_percent=float((change / allocated) * 100),
                            reason=f"Consistently overspending by {deviation_percent:.1f}%. Current spending: ${spent:.2f}",
                            priority="HIGH" if deviation_percent > 30 else "MEDIUM",
                        )
                    )

            # Consistent underspending (<-15% deviation)
            elif deviation_percent < -15:
                pattern = patterns.get(category)
                if pattern:
                    # Suggest decrease based on actual spending with buffer
                    suggested = spent * Decimal("1.1")  # 10% buffer above actual
                    change = suggested - allocated

                    suggestions.append(
                        BudgetSuggestion(
                            category=category,
                            current_allocation=allocated,
                            suggested_allocation=suggested,
                            change_amount=change,
                            change_percent=float((change / allocated) * 100),
                            reason=f"Consistently underspending by {abs(deviation_percent):.1f}%. Current spending: ${spent:.2f}",
                            priority="LOW",
                        )
                    )

        # Balance suggestions to maintain total budget
        if suggestions:
            suggestions = self._balance_suggestions(budget, suggestions)

        logger.info(
            "Budget optimizations suggested",
            user_id=str(user_id),
            budget_id=str(budget.id),
            suggestion_count=len(suggestions),
        )

        return suggestions

    def _balance_suggestions(
        self, budget: Budget, suggestions: List[BudgetSuggestion]
    ) -> List[BudgetSuggestion]:
        """Balance suggestions to maintain total budget constraint.

        Args:
            budget: Current budget
            suggestions: List of suggestions

        Returns:
            Balanced list of suggestions
        """
        # Calculate total change
        total_change = sum(s.change_amount for s in suggestions)

        # If total change is not zero, adjust suggestions proportionally
        if total_change != 0:
            # Find categories to adjust (prioritize low priority suggestions)
            adjustment_needed = -total_change

            # Sort by priority (LOW first for adjustments)
            sorted_suggestions = sorted(
                suggestions,
                key=lambda s: (s.priority == "HIGH", s.priority == "MEDIUM", s.priority == "LOW"),
            )

            # Distribute adjustment across low priority suggestions
            for suggestion in sorted_suggestions:
                if adjustment_needed == 0:
                    break

                if suggestion.priority == "LOW" and adjustment_needed > 0:
                    # Reduce the decrease amount
                    adjustment = min(abs(suggestion.change_amount), adjustment_needed)
                    suggestion.change_amount += adjustment
                    suggestion.suggested_allocation += adjustment
                    suggestion.change_percent = float(
                        (suggestion.change_amount / suggestion.current_allocation) * 100
                    )
                    adjustment_needed -= adjustment

        return suggestions

    async def apply_optimization(
        self,
        budget_id: UUID,
        user_id: UUID,
        suggestions: List[BudgetSuggestion],
        user_approved: bool,
    ) -> Optional[Budget]:
        """Apply budget optimization suggestions.

        Args:
            budget_id: Budget ID
            user_id: User ID
            suggestions: List of suggestions to apply
            user_approved: Whether user has approved the changes

        Returns:
            Updated budget if approved and applied, None otherwise

        Raises:
            ValueError: If user has not approved the changes
        """
        if not user_approved:
            raise ValueError("User approval required to apply budget optimizations")

        # Get budget
        stmt = select(Budget).where(and_(Budget.id == budget_id, Budget.user_id == user_id))
        result = await self.db.execute(stmt)
        budget = result.scalar_one_or_none()

        if not budget:
            return None

        # Apply suggestions
        new_allocations = dict(budget.allocations)
        for suggestion in suggestions:
            new_allocations[suggestion.category] = float(suggestion.suggested_allocation)

        budget.allocations = new_allocations
        budget.updated_at = datetime.now(timezone.utc)

        await self.db.flush()
        await self.db.refresh(budget)

        logger.info(
            "Budget optimization applied",
            budget_id=str(budget_id),
            user_id=str(user_id),
            suggestions_applied=len(suggestions),
        )

        return budget
