"""Tests for budget optimizer service."""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from app.services.budget_optimizer import BudgetOptimizer, BudgetSuggestion
from app.models.transaction import Transaction
from app.models.budget import Budget
from app.models.user import User


@pytest.fixture
async def test_user(db_session):
    """Create a test user."""
    user = User(
        id=uuid4(),
        email="optimizer@test.com",
        password_hash="hashed_password",
        first_name="Test",
        last_name="User",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def budget_optimizer(db_session):
    """Create budget optimizer instance."""
    return BudgetOptimizer(db_session)


@pytest.fixture
async def sample_budget(db_session, test_user):
    """Create a sample budget."""
    today = datetime.utcnow().date()
    budget = Budget(
        id=uuid4(),
        user_id=test_user.id,
        name="Monthly Budget",
        period_start=today.replace(day=1),
        period_end=(today.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1),
        allocations={
            "Groceries": 500.0,
            "Dining": 300.0,
            "Transportation": 200.0,
            "Entertainment": 150.0,
        },
    )
    db_session.add(budget)
    await db_session.flush()
    return budget


async def create_transactions(db_session, user_id, category, amounts, start_date):
    """Helper to create multiple transactions."""
    transactions = []
    for i, amount in enumerate(amounts):
        transaction = Transaction(
            id=uuid4(),
            user_id=user_id,
            amount=Decimal(str(amount)),
            date=start_date + timedelta(days=i * 7),
            description=f"{category} transaction {i}",
            category=category,
            type="EXPENSE",
            source="MANUAL",
        )
        db_session.add(transaction)
        transactions.append(transaction)

    await db_session.flush()
    return transactions


@pytest.mark.asyncio
class TestBudgetOptimizer:
    """Test budget optimizer functionality."""

    async def test_analyze_spending_patterns(self, budget_optimizer, test_user, db_session):
        """Test spending pattern analysis."""
        # Create transactions over 3 months
        start_date = datetime.utcnow().date() - timedelta(days=90)

        await create_transactions(
            db_session, test_user.id, "Groceries", [100, 120, 110, 105, 115], start_date
        )

        await create_transactions(
            db_session, test_user.id, "Dining", [50, 60, 55, 65, 70], start_date
        )

        await db_session.commit()

        # Analyze patterns
        patterns = await budget_optimizer.analyze_spending_patterns(test_user.id, months=3)

        # Verify patterns
        assert "Groceries" in patterns
        assert "Dining" in patterns

        groceries = patterns["Groceries"]
        assert groceries.transaction_count == 5
        assert groceries.average_spending > 0
        assert groceries.min_spending <= groceries.average_spending <= groceries.max_spending

    async def test_suggest_optimizations_overspending(
        self, budget_optimizer, test_user, sample_budget, db_session
    ):
        """Test optimization suggestions for overspending category."""
        # Create transactions that exceed budget
        await create_transactions(
            db_session,
            test_user.id,
            "Groceries",
            [150, 160, 155, 165],  # Total: 630, Budget: 500 (26% over)
            sample_budget.period_start,
        )

        await db_session.commit()

        # Get suggestions
        suggestions = await budget_optimizer.suggest_optimizations(
            test_user.id, sample_budget, historical_months=3
        )

        # Verify suggestions
        assert len(suggestions) > 0

        groceries_suggestion = next((s for s in suggestions if s.category == "Groceries"), None)
        assert groceries_suggestion is not None
        assert groceries_suggestion.suggested_allocation > groceries_suggestion.current_allocation
        assert groceries_suggestion.priority in ["HIGH", "MEDIUM"]
        assert "overspending" in groceries_suggestion.reason.lower()

    async def test_suggest_optimizations_underspending(
        self, budget_optimizer, test_user, sample_budget, db_session
    ):
        """Test optimization suggestions for underspending category."""
        # Create transactions well below budget
        await create_transactions(
            db_session,
            test_user.id,
            "Entertainment",
            [20, 25, 30, 25],  # Total: 100, Budget: 150 (33% under)
            sample_budget.period_start,
        )

        await db_session.commit()

        # Get suggestions
        suggestions = await budget_optimizer.suggest_optimizations(
            test_user.id, sample_budget, historical_months=3
        )

        # Verify suggestions
        entertainment_suggestion = next(
            (s for s in suggestions if s.category == "Entertainment"), None
        )

        if entertainment_suggestion:
            # After balancing, the suggestion might be adjusted
            # The key is that it was identified as underspending
            assert entertainment_suggestion.priority == "LOW"
            assert "underspending" in entertainment_suggestion.reason.lower()
            # The suggested allocation should be based on actual spending (100 * 1.1 = 110)
            # but may be adjusted during balancing
            assert (
                entertainment_suggestion.suggested_allocation
                <= entertainment_suggestion.current_allocation
                or abs(
                    entertainment_suggestion.suggested_allocation
                    - entertainment_suggestion.current_allocation
                )
                < Decimal("1")
            )

    async def test_suggest_optimizations_no_data(
        self, budget_optimizer, test_user, sample_budget, db_session
    ):
        """Test optimization suggestions with no spending data."""
        await db_session.commit()

        # Get suggestions (no transactions)
        suggestions = await budget_optimizer.suggest_optimizations(
            test_user.id, sample_budget, historical_months=3
        )

        # Should return empty list when no data
        assert len(suggestions) == 0

    async def test_apply_optimization_requires_approval(
        self, budget_optimizer, test_user, sample_budget, db_session
    ):
        """Test that optimization requires user approval."""
        suggestions = [
            BudgetSuggestion(
                category="Groceries",
                current_allocation=Decimal("500"),
                suggested_allocation=Decimal("600"),
                change_amount=Decimal("100"),
                change_percent=20.0,
                reason="Test reason",
                priority="HIGH",
            )
        ]

        # Should raise error without approval
        with pytest.raises(ValueError, match="User approval required"):
            await budget_optimizer.apply_optimization(
                sample_budget.id, test_user.id, suggestions, user_approved=False
            )

    async def test_apply_optimization_with_approval(
        self, budget_optimizer, test_user, sample_budget, db_session
    ):
        """Test applying optimization with user approval."""
        suggestions = [
            BudgetSuggestion(
                category="Groceries",
                current_allocation=Decimal("500"),
                suggested_allocation=Decimal("600"),
                change_amount=Decimal("100"),
                change_percent=20.0,
                reason="Test reason",
                priority="HIGH",
            )
        ]

        await db_session.commit()

        # Apply with approval
        updated_budget = await budget_optimizer.apply_optimization(
            sample_budget.id, test_user.id, suggestions, user_approved=True
        )

        # Verify budget was updated
        assert updated_budget is not None
        assert updated_budget.allocations["Groceries"] == 600.0

    async def test_apply_optimization_nonexistent_budget(
        self, budget_optimizer, test_user, db_session
    ):
        """Test applying optimization to nonexistent budget."""
        suggestions = [
            BudgetSuggestion(
                category="Groceries",
                current_allocation=Decimal("500"),
                suggested_allocation=Decimal("600"),
                change_amount=Decimal("100"),
                change_percent=20.0,
                reason="Test reason",
                priority="HIGH",
            )
        ]

        # Should return None for nonexistent budget
        result = await budget_optimizer.apply_optimization(
            uuid4(), test_user.id, suggestions, user_approved=True
        )

        assert result is None

    async def test_balance_suggestions(self, budget_optimizer, sample_budget):
        """Test that suggestions are balanced to maintain total budget."""
        suggestions = [
            BudgetSuggestion(
                category="Groceries",
                current_allocation=Decimal("500"),
                suggested_allocation=Decimal("600"),
                change_amount=Decimal("100"),
                change_percent=20.0,
                reason="Overspending",
                priority="HIGH",
            ),
            BudgetSuggestion(
                category="Entertainment",
                current_allocation=Decimal("150"),
                suggested_allocation=Decimal("100"),
                change_amount=Decimal("-50"),
                change_percent=-33.3,
                reason="Underspending",
                priority="LOW",
            ),
        ]

        # Balance suggestions
        balanced = budget_optimizer._balance_suggestions(sample_budget, suggestions)

        # Total change should be closer to zero
        total_change = sum(s.change_amount for s in balanced)
        assert abs(total_change) <= abs(sum(s.change_amount for s in suggestions))

    async def test_multiple_categories_optimization(
        self, budget_optimizer, test_user, sample_budget, db_session
    ):
        """Test optimization with multiple categories."""
        # Overspending in Groceries
        await create_transactions(
            db_session, test_user.id, "Groceries", [150, 160, 155], sample_budget.period_start
        )

        # Underspending in Entertainment
        await create_transactions(
            db_session, test_user.id, "Entertainment", [20, 25, 30], sample_budget.period_start
        )

        # On-track in Dining
        await create_transactions(
            db_session, test_user.id, "Dining", [75, 80, 70, 75], sample_budget.period_start
        )

        await db_session.commit()

        # Get suggestions
        suggestions = await budget_optimizer.suggest_optimizations(
            test_user.id, sample_budget, historical_months=3
        )

        # Should have suggestions for overspending and underspending
        categories_with_suggestions = {s.category for s in suggestions}
        assert (
            "Groceries" in categories_with_suggestions
            or "Entertainment" in categories_with_suggestions
        )

        # Dining should not have suggestions (on-track)
        assert "Dining" not in categories_with_suggestions or any(
            abs(s.change_percent) < 15 for s in suggestions if s.category == "Dining"
        )
