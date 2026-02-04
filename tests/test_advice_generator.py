"""Tests for advice generator service."""

import pytest
from datetime import datetime, timedelta, date
from decimal import Decimal
from uuid import uuid4

from app.services.advice_generator import AdviceGenerator, AdvicePriority
from app.models.transaction import Transaction
from app.models.budget import Budget
from app.models.financial_goal import FinancialGoal
from app.models.user import User


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


@pytest.mark.asyncio
class TestAdviceGenerator:
    """Test suite for AdviceGenerator."""
    
    async def test_generate_dashboard_advice_minimum_count(self, db_session, test_user):
        """Test that dashboard advice generates at least 3 recommendations."""
        service = AdviceGenerator(db_session)
        
        # Generate advice for user with no data
        advice_list = await service.generate_dashboard_advice(test_user.id)
        
        # Should have at least 3 recommendations (general tips)
        assert len(advice_list) >= 3
        assert all(hasattr(a, 'explanation') for a in advice_list)
    
    async def test_check_spending_alerts_no_overspending(self, db_session, test_user):
        """Test spending alerts when no overspending occurs."""
        service = AdviceGenerator(db_session)
        
        # Create budget
        budget = Budget(
            user_id=test_user.id,
            name="Monthly Budget",
            period_start=date.today(),
            period_end=date.today() + timedelta(days=30),
            allocations={"Groceries": 500.0, "Dining": 200.0}
        )
        db_session.add(budget)
        await db_session.flush()
        
        # Add transactions within budget
        transaction1 = Transaction(
            user_id=test_user.id,
            amount=Decimal("100.00"),
            date=date.today(),
            description="Grocery store",
            category="Groceries",
            type="EXPENSE",
            source="MANUAL"
        )
        transaction2 = Transaction(
            user_id=test_user.id,
            amount=Decimal("50.00"),
            date=date.today(),
            description="Restaurant",
            category="Dining",
            type="EXPENSE",
            source="MANUAL"
        )
        db_session.add_all([transaction1, transaction2])
        await db_session.commit()
        
        # Check alerts
        alerts = await service.check_spending_alerts(test_user.id)
        
        # Should have no alerts
        assert len(alerts) == 0
    
    async def test_check_spending_alerts_moderate_overspending(self, db_session, test_user):
        """Test spending alerts for moderate overspending (10-20%)."""
        service = AdviceGenerator(db_session)
        
        # Create budget
        budget = Budget(
            user_id=test_user.id,
            name="Monthly Budget",
            period_start=date.today(),
            period_end=date.today() + timedelta(days=30),
            allocations={"Groceries": 500.0}
        )
        db_session.add(budget)
        await db_session.flush()
        
        # Add transactions exceeding budget by 15%
        transaction = Transaction(
            user_id=test_user.id,
            amount=Decimal("575.00"),  # 15% over budget
            date=date.today(),
            description="Grocery store",
            category="Groceries",
            type="EXPENSE",
            source="MANUAL"
        )
        db_session.add(transaction)
        await db_session.commit()
        
        # Check alerts
        alerts = await service.check_spending_alerts(test_user.id)
        
        # Should have one HIGH priority alert
        assert len(alerts) == 1
        assert alerts[0].priority == AdvicePriority.HIGH
        assert "Groceries" in alerts[0].title
        assert alerts[0].category == "Groceries"
        assert alerts[0].explanation is not None
        assert len(alerts[0].action_items) > 0
    
    async def test_check_spending_alerts_critical_overspending(self, db_session, test_user):
        """Test spending alerts for critical overspending (>20%)."""
        service = AdviceGenerator(db_session)
        
        # Create budget
        budget = Budget(
            user_id=test_user.id,
            name="Monthly Budget",
            period_start=date.today(),
            period_end=date.today() + timedelta(days=30),
            allocations={"Dining": 200.0}
        )
        db_session.add(budget)
        await db_session.flush()
        
        # Add transactions exceeding budget by 25%
        transaction = Transaction(
            user_id=test_user.id,
            amount=Decimal("250.00"),  # 25% over budget
            date=date.today(),
            description="Restaurant",
            category="Dining",
            type="EXPENSE",
            source="MANUAL"
        )
        db_session.add(transaction)
        await db_session.commit()
        
        # Check alerts
        alerts = await service.check_spending_alerts(test_user.id)
        
        # Should have one CRITICAL priority alert
        assert len(alerts) == 1
        assert alerts[0].priority == AdvicePriority.CRITICAL
        assert "Dining" in alerts[0].title
        assert "critically" in alerts[0].message.lower()
    
    async def test_check_spending_alerts_multiple_categories(self, db_session, test_user):
        """Test spending alerts for multiple overspending categories."""
        service = AdviceGenerator(db_session)
        
        # Create budget
        budget = Budget(
            user_id=test_user.id,
            name="Monthly Budget",
            period_start=date.today(),
            period_end=date.today() + timedelta(days=30),
            allocations={"Groceries": 500.0, "Dining": 200.0, "Entertainment": 100.0}
        )
        db_session.add(budget)
        await db_session.flush()
        
        # Add overspending transactions in multiple categories
        transactions = [
            Transaction(
                user_id=test_user.id,
                amount=Decimal("575.00"),  # 15% over
                date=date.today(),
                description="Grocery store",
                category="Groceries",
                type="EXPENSE",
                source="MANUAL"
            ),
            Transaction(
                user_id=test_user.id,
                amount=Decimal("250.00"),  # 25% over
                date=date.today(),
                description="Restaurant",
                category="Dining",
                type="EXPENSE",
                source="MANUAL"
            )
        ]
        db_session.add_all(transactions)
        await db_session.commit()
        
        # Check alerts
        alerts = await service.check_spending_alerts(test_user.id)
        
        # Should have two alerts
        assert len(alerts) == 2
        categories = {alert.category for alert in alerts}
        assert "Groceries" in categories
        assert "Dining" in categories
    
    async def test_suggest_savings_opportunities_high_spending_category(self, db_session, test_user):
        """Test savings opportunities for high-spending categories."""
        service = AdviceGenerator(db_session)
        
        # Add transactions with one category dominating spending
        transactions = [
            Transaction(
                user_id=test_user.id,
                amount=Decimal("500.00"),
                date=date.today() - timedelta(days=i),
                description=f"Dining transaction {i}",
                category="Dining",
                type="EXPENSE",
                source="MANUAL"
            )
            for i in range(10)
        ]
        # Add smaller amounts in other categories
        transactions.append(
            Transaction(
                user_id=test_user.id,
                amount=Decimal("100.00"),
                date=date.today(),
                description="Groceries",
                category="Groceries",
                type="EXPENSE",
                source="MANUAL"
            )
        )
        db_session.add_all(transactions)
        await db_session.commit()
        
        # Get savings opportunities
        opportunities = await service.suggest_savings_opportunities(test_user.id)
        
        # Should suggest savings in Dining (>15% of total)
        assert len(opportunities) > 0
        dining_advice = [o for o in opportunities if o.category == "Dining"]
        assert len(dining_advice) > 0
        assert dining_advice[0].priority == AdvicePriority.MEDIUM
        assert "10%" in dining_advice[0].explanation
        assert len(dining_advice[0].action_items) > 0
    
    async def test_suggest_savings_opportunities_no_data(self, db_session, test_user):
        """Test savings opportunities with no transaction data."""
        service = AdviceGenerator(db_session)
        
        # Get savings opportunities with no transactions
        opportunities = await service.suggest_savings_opportunities(test_user.id)
        
        # Should return empty list
        assert len(opportunities) == 0
    
    async def test_goal_progress_at_risk(self, db_session, test_user):
        """Test advice for goals at risk of not being achieved."""
        service = AdviceGenerator(db_session)
        
        # Create goal that's behind schedule
        goal = FinancialGoal(
            user_id=test_user.id,
            name="Vacation Fund",
            target_amount=Decimal("2000.00"),
            current_amount=Decimal("400.00"),  # Only 20% progress
            deadline=date.today() + timedelta(days=30),  # 30 days left
            status="ACTIVE",
            created_at=datetime.utcnow() - timedelta(days=60)  # Started 60 days ago
        )
        db_session.add(goal)
        await db_session.commit()
        
        # Generate dashboard advice
        advice_list = await service.generate_dashboard_advice(test_user.id)
        
        # Should include goal at risk advice
        goal_advice = [a for a in advice_list if "at Risk" in a.title]
        assert len(goal_advice) > 0
        assert goal_advice[0].priority == AdvicePriority.HIGH
        assert "Vacation Fund" in goal_advice[0].title
        assert goal_advice[0].explanation is not None
    
    async def test_goal_progress_on_track(self, db_session, test_user):
        """Test advice for goals that are on track."""
        service = AdviceGenerator(db_session)
        
        # Create goal with good progress
        goal = FinancialGoal(
            user_id=test_user.id,
            name="Emergency Fund",
            target_amount=Decimal("1000.00"),
            current_amount=Decimal("800.00"),  # 80% progress
            deadline=date.today() + timedelta(days=30),
            status="ACTIVE",
            created_at=datetime.utcnow() - timedelta(days=30)
        )
        db_session.add(goal)
        await db_session.commit()
        
        # Generate dashboard advice
        advice_list = await service.generate_dashboard_advice(test_user.id)
        
        # Should include positive progress advice
        progress_advice = [a for a in advice_list if "Great Progress" in a.title]
        assert len(progress_advice) > 0
        assert progress_advice[0].priority == AdvicePriority.LOW
        assert "80" in progress_advice[0].message
    
    async def test_achievement_celebration(self, db_session, test_user):
        """Test advice for recently achieved goals."""
        service = AdviceGenerator(db_session)
        
        # Create recently achieved goal
        goal = FinancialGoal(
            user_id=test_user.id,
            name="New Laptop",
            target_amount=Decimal("1500.00"),
            current_amount=Decimal("1500.00"),
            deadline=date.today(),
            status="ACHIEVED",
            created_at=datetime.utcnow() - timedelta(days=60),
            updated_at=datetime.utcnow() - timedelta(days=2)  # Achieved 2 days ago
        )
        db_session.add(goal)
        await db_session.commit()
        
        # Generate dashboard advice
        advice_list = await service.generate_dashboard_advice(test_user.id)
        
        # Should include achievement celebration
        achievement_advice = [a for a in advice_list if "🎉" in a.title or "Achieved" in a.title]
        assert len(achievement_advice) > 0
        assert achievement_advice[0].priority == AdvicePriority.LOW
        assert "Congratulations" in achievement_advice[0].message
    
    async def test_general_tips_for_new_users(self, db_session, test_user):
        """Test general tips for users with few transactions."""
        service = AdviceGenerator(db_session)
        
        # Add only a few transactions
        transactions = [
            Transaction(
                user_id=test_user.id,
                amount=Decimal("50.00"),
                date=date.today() - timedelta(days=i),
                description=f"Transaction {i}",
                category="Groceries",
                type="EXPENSE",
                source="MANUAL"
            )
            for i in range(5)
        ]
        db_session.add_all(transactions)
        await db_session.commit()
        
        # Generate dashboard advice
        advice_list = await service.generate_dashboard_advice(test_user.id)
        
        # Should include tip about tracking more transactions
        tracking_advice = [a for a in advice_list if "Track More" in a.title]
        assert len(tracking_advice) > 0
        assert tracking_advice[0].priority == AdvicePriority.LOW
    
    async def test_advice_priority_ordering(self, db_session, test_user):
        """Test that advice is properly ordered by priority."""
        service = AdviceGenerator(db_session)
        
        # Create scenario with multiple priority levels
        # 1. Critical overspending
        budget = Budget(
            user_id=test_user.id,
            name="Monthly Budget",
            period_start=date.today(),
            period_end=date.today() + timedelta(days=30),
            allocations={"Dining": 200.0}
        )
        db_session.add(budget)
        await db_session.flush()
        
        transaction = Transaction(
            user_id=test_user.id,
            amount=Decimal("250.00"),  # 25% over
            date=date.today(),
            description="Restaurant",
            category="Dining",
            type="EXPENSE",
            source="MANUAL"
        )
        db_session.add(transaction)
        
        # 2. Goal at risk
        goal = FinancialGoal(
            user_id=test_user.id,
            name="Vacation",
            target_amount=Decimal("2000.00"),
            current_amount=Decimal("400.00"),
            deadline=date.today() + timedelta(days=30),
            status="ACTIVE",
            created_at=datetime.utcnow() - timedelta(days=60)
        )
        db_session.add(goal)
        await db_session.commit()
        
        # Generate advice
        advice_list = await service.generate_dashboard_advice(test_user.id, max_recommendations=5)
        
        # Verify ordering: CRITICAL should come before HIGH, HIGH before MEDIUM, etc.
        priorities = [a.priority for a in advice_list]
        priority_values = [
            {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}[p]
            for p in priorities
        ]
        assert priority_values == sorted(priority_values)
    
    async def test_advice_explanation_completeness(self, db_session, test_user):
        """Test that all advice includes explanations."""
        service = AdviceGenerator(db_session)
        
        # Create budget with overspending
        budget = Budget(
            user_id=test_user.id,
            name="Monthly Budget",
            period_start=date.today(),
            period_end=date.today() + timedelta(days=30),
            allocations={"Groceries": 500.0}
        )
        db_session.add(budget)
        await db_session.flush()
        
        transaction = Transaction(
            user_id=test_user.id,
            amount=Decimal("575.00"),
            date=date.today(),
            description="Grocery store",
            category="Groceries",
            type="EXPENSE",
            source="MANUAL"
        )
        db_session.add(transaction)
        await db_session.commit()
        
        # Generate all types of advice
        advice_list = await service.generate_dashboard_advice(test_user.id)
        
        # Verify all advice has explanations
        for advice in advice_list:
            assert advice.explanation is not None
            assert len(advice.explanation) > 0
            assert advice.title is not None
            assert advice.message is not None
    
    async def test_specific_budget_alert_check(self, db_session, test_user):
        """Test checking alerts for a specific budget."""
        service = AdviceGenerator(db_session)
        
        # Create two budgets
        budget1 = Budget(
            user_id=test_user.id,
            name="Budget 1",
            period_start=date.today(),
            period_end=date.today() + timedelta(days=30),
            allocations={"Groceries": 500.0}
        )
        budget2 = Budget(
            user_id=test_user.id,
            name="Budget 2",
            period_start=date.today() - timedelta(days=60),
            period_end=date.today() - timedelta(days=30),
            allocations={"Dining": 200.0}
        )
        db_session.add_all([budget1, budget2])
        await db_session.flush()
        
        # Add overspending to budget1
        transaction = Transaction(
            user_id=test_user.id,
            amount=Decimal("575.00"),
            date=date.today(),
            description="Grocery store",
            category="Groceries",
            type="EXPENSE",
            source="MANUAL"
        )
        db_session.add(transaction)
        await db_session.commit()
        
        # Check alerts for specific budget
        alerts = await service.check_spending_alerts(test_user.id, budget_id=budget1.id)
        
        # Should only have alert for budget1
        assert len(alerts) == 1
        assert alerts[0].related_id == budget1.id
