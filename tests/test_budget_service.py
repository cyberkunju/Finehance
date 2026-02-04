"""Tests for budget service."""

import pytest
from datetime import datetime, timedelta, date
from decimal import Decimal
from uuid import uuid4

from app.services.budget_service import BudgetService, BudgetProgress, BudgetAlert
from app.models.budget import Budget
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.transaction import TransactionType


@pytest.fixture
async def test_user(db_session):
    """Create a test user."""
    user = User(
        id=uuid4(),
        email="test@example.com",
        password_hash="hashed_password",
        first_name="Test",
        last_name="User"
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def budget_service(db_session):
    """Create budget service instance."""
    return BudgetService(db_session)


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
            "Entertainment": 150.0
        }
    )
    db_session.add(budget)
    await db_session.flush()
    return budget


class TestCreateBudget:
    """Tests for budget creation."""
    
    async def test_create_budget_success(self, budget_service, test_user):
        """Test successful budget creation."""
        today = date.today()
        period_start = today.replace(day=1)
        period_end = (period_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        allocations = {
            "Groceries": Decimal("500.00"),
            "Dining": Decimal("300.00"),
            "Transportation": Decimal("200.00")
        }
        
        budget = await budget_service.create_budget(
            user_id=test_user.id,
            name="Test Budget",
            period_start=period_start,
            period_end=period_end,
            allocations=allocations
        )
        
        assert budget is not None
        assert budget.user_id == test_user.id
        assert budget.name == "Test Budget"
        assert budget.period_start == period_start
        assert budget.period_end == period_end
        assert len(budget.allocations) == 3
        assert budget.allocations["Groceries"] == 500.0
    
    async def test_create_budget_invalid_period(self, budget_service, test_user):
        """Test budget creation with invalid period."""
        today = date.today()
        period_start = today
        period_end = today - timedelta(days=1)  # End before start
        
        with pytest.raises(ValueError, match="period end must be after start"):
            await budget_service.create_budget(
                user_id=test_user.id,
                name="Invalid Budget",
                period_start=period_start,
                period_end=period_end,
                allocations={"Groceries": Decimal("500.00")}
            )


class TestGetBudget:
    """Tests for getting budgets."""
    
    async def test_get_existing_budget(self, budget_service, test_user, sample_budget):
        """Test getting an existing budget."""
        budget = await budget_service.get_budget(sample_budget.id, test_user.id)
        
        assert budget is not None
        assert budget.id == sample_budget.id
        assert budget.name == "Monthly Budget"
    
    async def test_get_nonexistent_budget(self, budget_service, test_user):
        """Test getting a nonexistent budget."""
        budget = await budget_service.get_budget(uuid4(), test_user.id)
        assert budget is None
    
    async def test_get_budget_wrong_user(self, budget_service, sample_budget, db_session):
        """Test getting budget with wrong user ID."""
        other_user = User(
            id=uuid4(),
            email="other@example.com",
            password_hash="hashed_password",
            first_name="Other",
            last_name="User"
        )
        db_session.add(other_user)
        await db_session.flush()
        
        budget = await budget_service.get_budget(sample_budget.id, other_user.id)
        assert budget is None


class TestListBudgets:
    """Tests for listing budgets."""
    
    async def test_list_budgets_empty(self, budget_service, test_user):
        """Test listing budgets when none exist."""
        budgets = await budget_service.list_budgets(test_user.id)
        assert budgets == []
    
    async def test_list_budgets(self, budget_service, test_user, sample_budget):
        """Test listing budgets."""
        budgets = await budget_service.list_budgets(test_user.id)
        
        assert len(budgets) == 1
        assert budgets[0].id == sample_budget.id
    
    async def test_list_active_budgets_only(self, budget_service, test_user, db_session):
        """Test listing only active budgets."""
        today = datetime.utcnow().date()
        
        # Create active budget (includes today)
        active_budget = Budget(
            id=uuid4(),
            user_id=test_user.id,
            name="Active Budget",
            period_start=today - timedelta(days=5),
            period_end=today + timedelta(days=25),
            allocations={"Groceries": 500.0}
        )
        db_session.add(active_budget)
        
        # Create past budget
        past_budget = Budget(
            id=uuid4(),
            user_id=test_user.id,
            name="Past Budget",
            period_start=today - timedelta(days=60),
            period_end=today - timedelta(days=30),
            allocations={"Groceries": 500.0}
        )
        db_session.add(past_budget)
        
        await db_session.flush()
        
        # List all budgets
        all_budgets = await budget_service.list_budgets(test_user.id, active_only=False)
        assert len(all_budgets) == 2
        
        # List only active budgets
        active_budgets = await budget_service.list_budgets(test_user.id, active_only=True)
        assert len(active_budgets) == 1
        assert active_budgets[0].name == "Active Budget"


class TestBudgetProgress:
    """Tests for budget progress tracking."""
    
    async def test_get_budget_progress_no_spending(
        self, budget_service, test_user, sample_budget
    ):
        """Test budget progress with no spending."""
        progress = await budget_service.get_budget_progress(test_user.id, sample_budget.id)
        
        assert len(progress) == 4  # 4 categories
        assert "Groceries" in progress
        
        groceries_progress = progress["Groceries"]
        assert groceries_progress.allocated == Decimal("500.00")
        assert groceries_progress.spent == Decimal("0")
        assert groceries_progress.remaining == Decimal("500.00")
        assert groceries_progress.percent_used == 0
        assert groceries_progress.status == "ON_TRACK"
    
    async def test_get_budget_progress_with_spending(
        self, budget_service, test_user, sample_budget, db_session
    ):
        """Test budget progress with some spending."""
        # Add transactions
        transaction = Transaction(
            id=uuid4(),
            user_id=test_user.id,
            amount=Decimal("250.00"),
            date=sample_budget.period_start + timedelta(days=5),
            description="Grocery shopping",
            category="Groceries",
            type=TransactionType.EXPENSE.value,
            source="MANUAL"
        )
        db_session.add(transaction)
        await db_session.flush()
        
        progress = await budget_service.get_budget_progress(test_user.id, sample_budget.id)
        
        groceries_progress = progress["Groceries"]
        assert groceries_progress.spent == Decimal("250.00")
        assert groceries_progress.remaining == Decimal("250.00")
        assert groceries_progress.percent_used == 50.0
        assert groceries_progress.status == "ON_TRACK"
    
    async def test_get_budget_progress_warning_status(
        self, budget_service, test_user, sample_budget, db_session
    ):
        """Test budget progress with warning status (>80%)."""
        # Add transaction that uses 85% of budget
        transaction = Transaction(
            id=uuid4(),
            user_id=test_user.id,
            amount=Decimal("425.00"),  # 85% of 500
            date=sample_budget.period_start + timedelta(days=5),
            description="Grocery shopping",
            category="Groceries",
            type=TransactionType.EXPENSE.value,
            source="MANUAL"
        )
        db_session.add(transaction)
        await db_session.flush()
        
        progress = await budget_service.get_budget_progress(test_user.id, sample_budget.id)
        
        groceries_progress = progress["Groceries"]
        assert groceries_progress.status == "WARNING"
        assert groceries_progress.percent_used == 85.0
    
    async def test_get_budget_progress_exceeded_status(
        self, budget_service, test_user, sample_budget, db_session
    ):
        """Test budget progress with exceeded status (>100%)."""
        # Add transaction that exceeds budget
        transaction = Transaction(
            id=uuid4(),
            user_id=test_user.id,
            amount=Decimal("600.00"),  # 120% of 500
            date=sample_budget.period_start + timedelta(days=5),
            description="Grocery shopping",
            category="Groceries",
            type=TransactionType.EXPENSE.value,
            source="MANUAL"
        )
        db_session.add(transaction)
        await db_session.flush()
        
        progress = await budget_service.get_budget_progress(test_user.id, sample_budget.id)
        
        groceries_progress = progress["Groceries"]
        assert groceries_progress.status == "EXCEEDED"
        assert groceries_progress.percent_used == 120.0
        assert groceries_progress.remaining == Decimal("-100.00")


class TestBudgetAlerts:
    """Tests for budget alerts."""
    
    async def test_check_budget_alerts_no_alerts(
        self, budget_service, test_user, sample_budget
    ):
        """Test budget alerts with no overspending."""
        alerts = await budget_service.check_budget_alerts(test_user.id, sample_budget.id)
        assert alerts == []
    
    async def test_check_budget_alerts_warning(
        self, budget_service, test_user, sample_budget, db_session
    ):
        """Test budget alerts with warning level (>80%)."""
        # Add transaction that uses 85% of budget
        transaction = Transaction(
            id=uuid4(),
            user_id=test_user.id,
            amount=Decimal("425.00"),
            date=sample_budget.period_start + timedelta(days=5),
            description="Grocery shopping",
            category="Groceries",
            type=TransactionType.EXPENSE.value,
            source="MANUAL"
        )
        db_session.add(transaction)
        await db_session.flush()
        
        alerts = await budget_service.check_budget_alerts(test_user.id, sample_budget.id)
        
        assert len(alerts) == 1
        alert = alerts[0]
        assert alert.category == "Groceries"
        assert alert.severity == "WARNING"
        assert "Approaching budget limit" in alert.message
    
    async def test_check_budget_alerts_critical(
        self, budget_service, test_user, sample_budget, db_session
    ):
        """Test budget alerts with critical level (>100%)."""
        # Add transaction that exceeds budget
        transaction = Transaction(
            id=uuid4(),
            user_id=test_user.id,
            amount=Decimal("600.00"),
            date=sample_budget.period_start + timedelta(days=5),
            description="Grocery shopping",
            category="Groceries",
            type=TransactionType.EXPENSE.value,
            source="MANUAL"
        )
        db_session.add(transaction)
        await db_session.flush()
        
        alerts = await budget_service.check_budget_alerts(test_user.id, sample_budget.id)
        
        assert len(alerts) == 1
        alert = alerts[0]
        assert alert.category == "Groceries"
        assert alert.severity == "CRITICAL"
        assert "Budget exceeded" in alert.message
        assert alert.percent_over == 20.0  # 120% - 100%


class TestUpdateBudget:
    """Tests for budget updates."""
    
    async def test_update_budget_name(self, budget_service, test_user, sample_budget):
        """Test updating budget name."""
        updated = await budget_service.update_budget(
            budget_id=sample_budget.id,
            user_id=test_user.id,
            name="Updated Budget Name"
        )
        
        assert updated is not None
        assert updated.name == "Updated Budget Name"
        assert updated.allocations == sample_budget.allocations
    
    async def test_update_budget_allocations(self, budget_service, test_user, sample_budget):
        """Test updating budget allocations."""
        new_allocations = {
            "Groceries": Decimal("600.00"),
            "Dining": Decimal("400.00")
        }
        
        updated = await budget_service.update_budget(
            budget_id=sample_budget.id,
            user_id=test_user.id,
            allocations=new_allocations
        )
        
        assert updated is not None
        assert updated.allocations["Groceries"] == 600.0
        assert updated.allocations["Dining"] == 400.0
    
    async def test_update_nonexistent_budget(self, budget_service, test_user):
        """Test updating nonexistent budget."""
        updated = await budget_service.update_budget(
            budget_id=uuid4(),
            user_id=test_user.id,
            name="New Name"
        )
        
        assert updated is None


class TestDeleteBudget:
    """Tests for budget deletion."""
    
    async def test_delete_budget_success(self, budget_service, test_user, sample_budget):
        """Test successful budget deletion."""
        result = await budget_service.delete_budget(sample_budget.id, test_user.id)
        assert result is True
        
        # Verify budget is deleted
        budget = await budget_service.get_budget(sample_budget.id, test_user.id)
        assert budget is None
    
    async def test_delete_nonexistent_budget(self, budget_service, test_user):
        """Test deleting nonexistent budget."""
        result = await budget_service.delete_budget(uuid4(), test_user.id)
        assert result is False
