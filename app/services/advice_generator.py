"""Advice generator service for personalized financial recommendations."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional
from uuid import UUID
from dataclasses import dataclass
from enum import Enum

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Transaction
from app.models.budget import Budget
from app.models.financial_goal import FinancialGoal
from app.logging_config import get_logger

logger = get_logger(__name__)


class AdvicePriority(str, Enum):
    """Advice priority levels."""

    CRITICAL = "CRITICAL"  # Budget exceeded by >20%
    HIGH = "HIGH"  # Savings rate below target, recurring overspending
    MEDIUM = "MEDIUM"  # Optimization opportunities, goal progress
    LOW = "LOW"  # General tips, achievements


@dataclass
class Advice:
    """Financial advice recommendation."""

    title: str
    message: str
    explanation: str
    priority: AdvicePriority
    category: Optional[str] = None
    action_items: Optional[List[str]] = None
    related_id: Optional[UUID] = None  # Budget ID, Goal ID, etc.


class AdviceGenerator:
    """Service for generating personalized financial recommendations."""

    def __init__(self, db: AsyncSession):
        """Initialize advice generator.

        Args:
            db: Database session
        """
        self.db = db

    async def generate_dashboard_advice(
        self, user_id: UUID, max_recommendations: int = 3
    ) -> List[Advice]:
        """Generate top priority recommendations for dashboard.

        Args:
            user_id: User ID
            max_recommendations: Maximum number of recommendations (default: 3)

        Returns:
            List of Advice objects, sorted by priority
        """
        all_advice = []

        # Check spending alerts
        spending_alerts = await self.check_spending_alerts(user_id)
        all_advice.extend(spending_alerts)

        # Check goal progress
        goal_advice = await self._check_goal_progress(user_id)
        all_advice.extend(goal_advice)

        # Check savings opportunities
        savings_advice = await self.suggest_savings_opportunities(user_id)
        all_advice.extend(savings_advice)

        # Check for achievements
        achievement_advice = await self._check_achievements(user_id)
        all_advice.extend(achievement_advice)

        # Sort by priority and return top recommendations
        priority_order = {
            AdvicePriority.CRITICAL: 0,
            AdvicePriority.HIGH: 1,
            AdvicePriority.MEDIUM: 2,
            AdvicePriority.LOW: 3,
        }

        sorted_advice = sorted(all_advice, key=lambda a: priority_order[a.priority])

        # Ensure at least 3 recommendations if possible
        if len(sorted_advice) < max_recommendations:
            # Add general tips if needed
            general_tips = await self._generate_general_tips(user_id)
            sorted_advice.extend(general_tips)

        return sorted_advice[:max_recommendations]

    async def check_spending_alerts(
        self, user_id: UUID, budget_id: Optional[UUID] = None
    ) -> List[Advice]:
        """Generate warnings for budget overruns.

        Args:
            user_id: User ID
            budget_id: Optional specific budget ID to check

        Returns:
            List of spending alert advice
        """
        advice_list = []

        # Get active budgets
        if budget_id:
            stmt = select(Budget).where(and_(Budget.id == budget_id, Budget.user_id == user_id))
        else:
            # Get current active budgets
            today = datetime.now(timezone.utc).date()
            stmt = select(Budget).where(
                and_(
                    Budget.user_id == user_id,
                    Budget.period_start <= today,
                    Budget.period_end >= today,
                )
            )

        result = await self.db.execute(stmt)
        budgets = result.scalars().all()

        for budget in budgets:
            # Calculate spending for each category
            for category, allocated_amount in budget.allocations.items():
                allocated = Decimal(str(allocated_amount))

                # Get actual spending
                stmt = select(func.sum(Transaction.amount)).where(
                    and_(
                        Transaction.user_id == user_id,
                        Transaction.category == category,
                        Transaction.type == "EXPENSE",
                        Transaction.date >= budget.period_start,
                        Transaction.date <= budget.period_end,
                        Transaction.deleted_at.is_(None),
                    )
                )
                result = await self.db.execute(stmt)
                spent = result.scalar() or Decimal(0)

                # Check for overspending (>10% threshold)
                if spent > allocated * Decimal("1.1"):
                    percent_over = float((spent / allocated - 1) * 100)

                    # Determine priority
                    if percent_over >= 20:
                        priority = AdvicePriority.CRITICAL
                        severity = "critically"
                    else:
                        priority = AdvicePriority.HIGH
                        severity = "significantly"

                    advice = Advice(
                        title=f"{category} Budget Alert",
                        message=f"You've {severity} exceeded your {category} budget",
                        explanation=(
                            f"Your {category} spending is ${spent:.2f}, which is "
                            f"{percent_over:.1f}% over your budget of ${allocated:.2f}. "
                            f"This overspending may impact your financial goals."
                        ),
                        priority=priority,
                        category=category,
                        action_items=[
                            f"Review recent {category} transactions",
                            f"Consider reducing {category} spending",
                            "Adjust budget allocation if this is a recurring pattern",
                        ],
                        related_id=budget.id,
                    )

                    advice_list.append(advice)

                    logger.info(
                        "Spending alert generated",
                        user_id=str(user_id),
                        category=category,
                        spent=float(spent),
                        allocated=float(allocated),
                        percent_over=percent_over,
                    )

        return advice_list

    async def suggest_savings_opportunities(
        self, user_id: UUID, lookback_months: int = 3
    ) -> List[Advice]:
        """Identify categories where user can reduce spending.

        Args:
            user_id: User ID
            lookback_months: Number of months to analyze (default: 3)

        Returns:
            List of savings opportunity advice
        """
        advice_list = []

        # Calculate date range
        end_date = datetime.now(timezone.utc).date()
        start_date = end_date - timedelta(days=lookback_months * 30)

        # Get spending by category
        stmt = (
            select(
                Transaction.category,
                func.sum(Transaction.amount).label("total_spent"),
                func.count(Transaction.id).label("transaction_count"),
                func.avg(Transaction.amount).label("avg_amount"),
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
        spending_data = result.all()

        # Calculate total spending
        total_spending = sum(row.total_spent for row in spending_data)

        if total_spending == 0:
            return advice_list

        # Identify high-spending categories (>15% of total)
        for row in spending_data:
            category_percent = (row.total_spent / total_spending) * 100

            if category_percent > 15:
                # Suggest savings opportunity
                potential_savings = row.total_spent * Decimal("0.1")  # 10% reduction

                advice = Advice(
                    title=f"Savings Opportunity: {row.category}",
                    message=f"Consider reducing {row.category} spending",
                    explanation=(
                        f"{row.category} represents {category_percent:.1f}% of your total spending "
                        f"(${row.total_spent:.2f} over the last {lookback_months} months). "
                        f"Reducing this by just 10% could save you ${potential_savings:.2f}."
                    ),
                    priority=AdvicePriority.MEDIUM,
                    category=row.category,
                    action_items=[
                        f"Review your {row.category} transactions for unnecessary expenses",
                        f"Look for cheaper alternatives in {row.category}",
                        f"Set a lower budget for {row.category} next period",
                    ],
                )

                advice_list.append(advice)

        return advice_list

    async def _check_goal_progress(self, user_id: UUID) -> List[Advice]:
        """Check financial goal progress and generate advice.

        Args:
            user_id: User ID

        Returns:
            List of goal-related advice
        """
        advice_list = []

        # Get active goals
        stmt = select(FinancialGoal).where(
            and_(FinancialGoal.user_id == user_id, FinancialGoal.status == "ACTIVE")
        )
        result = await self.db.execute(stmt)
        goals = result.scalars().all()

        today = datetime.now(timezone.utc).date()

        for goal in goals:
            progress_percent = float((goal.current_amount / goal.target_amount) * 100)

            # Check if goal is at risk
            if goal.deadline:
                days_remaining = (goal.deadline - today).days

                if days_remaining > 0:
                    # Calculate required daily savings
                    remaining_amount = goal.target_amount - goal.current_amount
                    required_daily = remaining_amount / days_remaining

                    # Check if goal is at risk (less than 50% progress with less than 50% time remaining)
                    total_days = (goal.deadline - goal.created_at.date()).days
                    if total_days > 0:
                        time_elapsed_percent = (
                            (today - goal.created_at.date()).days / total_days
                        ) * 100
                    else:
                        time_elapsed_percent = 100.0  # Goal deadline is today or already passed

                    if time_elapsed_percent > 50 and progress_percent < 50:
                        advice = Advice(
                            title=f"Goal at Risk: {goal.name}",
                            message=f"Your '{goal.name}' goal may not be achieved by the deadline",
                            explanation=(
                                f"You're {progress_percent:.1f}% towards your goal of ${goal.target_amount:.2f}, "
                                f"but only {days_remaining} days remain. You need to save ${required_daily:.2f} per day "
                                f"to reach your target."
                            ),
                            priority=AdvicePriority.HIGH,
                            action_items=[
                                f"Increase savings rate to ${required_daily:.2f} per day",
                                "Review and reduce discretionary spending",
                                "Consider extending the deadline if needed",
                            ],
                            related_id=goal.id,
                        )
                        advice_list.append(advice)

                    # Positive progress update
                    elif progress_percent >= 75:
                        advice = Advice(
                            title=f"Great Progress: {goal.name}",
                            message=f"You're {progress_percent:.1f}% towards your goal!",
                            explanation=(
                                f"You've saved ${goal.current_amount:.2f} of ${goal.target_amount:.2f}. "
                                f"Keep up the great work! Only ${goal.target_amount - goal.current_amount:.2f} to go."
                            ),
                            priority=AdvicePriority.LOW,
                            action_items=[
                                "Maintain your current savings rate",
                                "Consider setting a new goal once this is achieved",
                            ],
                            related_id=goal.id,
                        )
                        advice_list.append(advice)

        return advice_list

    async def _check_achievements(self, user_id: UUID) -> List[Advice]:
        """Check for financial achievements to celebrate.

        Args:
            user_id: User ID

        Returns:
            List of achievement advice
        """
        advice_list = []

        # Check for recently achieved goals (within last 7 days)
        seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)

        stmt = select(FinancialGoal).where(
            and_(
                FinancialGoal.user_id == user_id,
                FinancialGoal.status == "ACHIEVED",
                FinancialGoal.updated_at >= seven_days_ago,
            )
        )
        result = await self.db.execute(stmt)
        achieved_goals = result.scalars().all()

        for goal in achieved_goals:
            advice = Advice(
                title=f"🎉 Goal Achieved: {goal.name}",
                message=f"Congratulations! You've reached your goal of ${goal.target_amount:.2f}",
                explanation=(
                    f"You successfully saved ${goal.target_amount:.2f} for {goal.name}. "
                    f"This is a significant financial achievement!"
                ),
                priority=AdvicePriority.LOW,
                action_items=[
                    "Consider setting a new financial goal",
                    "Maintain your savings discipline",
                    "Celebrate your achievement responsibly",
                ],
                related_id=goal.id,
            )
            advice_list.append(advice)

        return advice_list

    async def _generate_general_tips(self, user_id: UUID) -> List[Advice]:
        """Generate general financial tips.

        Args:
            user_id: User ID

        Returns:
            List of general tip advice
        """
        advice_list = []

        # Get user's transaction count
        stmt = select(func.count(Transaction.id)).where(
            and_(Transaction.user_id == user_id, Transaction.deleted_at.is_(None))
        )
        result = await self.db.execute(stmt)
        transaction_count = result.scalar() or 0

        # Tip for new users
        if transaction_count < 20:
            advice = Advice(
                title="Track More Transactions",
                message="Add more transactions to get better insights",
                explanation=(
                    "The more transactions you track, the better our AI can understand your "
                    "spending patterns and provide personalized recommendations."
                ),
                priority=AdvicePriority.LOW,
                action_items=[
                    "Add recent transactions manually",
                    "Consider connecting your bank account for automatic sync",
                    "Upload a bank statement file",
                ],
            )
            advice_list.append(advice)

        # General savings tip
        advice = Advice(
            title="Build an Emergency Fund",
            message="Aim to save 3-6 months of expenses",
            explanation=(
                "An emergency fund provides financial security and peace of mind. "
                "Start by setting a goal to save one month of expenses, then gradually increase it."
            ),
            priority=AdvicePriority.LOW,
            action_items=[
                "Calculate your monthly expenses",
                "Set up automatic transfers to savings",
                "Create a financial goal for your emergency fund",
            ],
        )
        advice_list.append(advice)

        # Budget planning tip
        advice = Advice(
            title="Create a Monthly Budget",
            message="Plan your spending with category-based budgets",
            explanation=(
                "A well-structured budget helps you control spending and reach your financial goals. "
                "Start by tracking your expenses for a month, then set realistic limits for each category."
            ),
            priority=AdvicePriority.LOW,
            action_items=[
                "Review your spending patterns by category",
                "Set budget limits for major expense categories",
                "Monitor your budget progress regularly",
            ],
        )
        advice_list.append(advice)

        return advice_list
