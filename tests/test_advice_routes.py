"""Tests for advice API endpoints."""

import pytest
from datetime import timedelta, date
from decimal import Decimal
from httpx import AsyncClient

from app.models.transaction import Transaction
from app.models.budget import Budget


@pytest.mark.asyncio
class TestAdviceRoutes:
    """Test advice API endpoints."""

    async def test_get_personalized_advice_empty(
        self, async_client: AsyncClient, test_user, test_db
    ):
        """Test advice generation with no data."""
        user_id = test_user.id

        response = await async_client.get(f"/api/advice?user_id={user_id}")

        assert response.status_code == 200
        data = response.json()
        # Should return at least general tips
        assert len(data) >= 1
        assert all("title" in advice for advice in data)
        assert all("message" in advice for advice in data)
        assert all("explanation" in advice for advice in data)
        assert all("priority" in advice for advice in data)

    async def test_get_personalized_advice_with_data(
        self, async_client: AsyncClient, test_user, test_db
    ):
        """Test advice generation with user data."""
        user_id = test_user.id

        # Create some transactions
        for i in range(10):
            transaction = Transaction(
                user_id=user_id,
                amount=Decimal("50.00"),
                type="EXPENSE",
                category="Groceries",
                description=f"Test {i}",
                date=date.today() - timedelta(days=i),
                source="MANUAL",
            )
            test_db.add(transaction)
        await test_db.commit()

        response = await async_client.get(f"/api/advice?user_id={user_id}")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

        # Check advice structure
        for advice in data:
            assert "title" in advice
            assert "message" in advice
            assert "explanation" in advice
            assert advice["priority"] in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]

    async def test_get_personalized_advice_max_recommendations(
        self, async_client: AsyncClient, test_user, test_db
    ):
        """Test advice with custom max recommendations."""
        user_id = test_user.id

        response = await async_client.get(f"/api/advice?user_id={user_id}&max_recommendations=5")

        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 5

    async def test_get_spending_alerts_no_budget(
        self, async_client: AsyncClient, test_user, test_db
    ):
        """Test spending alerts with no budgets."""
        user_id = test_user.id

        response = await async_client.get(f"/api/advice/spending-alerts?user_id={user_id}")

        assert response.status_code == 200
        data = response.json()
        assert data == []

    async def test_get_spending_alerts_with_overspending(
        self, async_client: AsyncClient, test_user, test_db
    ):
        """Test spending alerts with budget overspending."""
        user_id = test_user.id

        # Create budget that covers today
        today = date.today()
        budget = Budget(
            user_id=user_id,
            name="Monthly Budget",
            period_start=today.replace(day=1),
            period_end=today,  # Ensure budget covers today
            allocations={"Groceries": 200.00},
        )
        test_db.add(budget)
        await test_db.commit()

        # Create transactions that exceed budget (within budget period)
        for i in range(10):
            transaction = Transaction(
                user_id=user_id,
                amount=Decimal("30.00"),
                type="EXPENSE",
                category="Groceries",
                description=f"Overspending {i}",
                date=today - timedelta(days=i),
                source="MANUAL",
            )
            test_db.add(transaction)
        await test_db.commit()

        response = await async_client.get(f"/api/advice/spending-alerts?user_id={user_id}")

        assert response.status_code == 200
        data = response.json()
        # Should have at least one alert for overspending
        assert len(data) >= 1

        alert = data[0]
        assert "Groceries" in alert["title"]
        assert alert["priority"] in ["CRITICAL", "HIGH"]
        assert alert["category"] == "Groceries"
        assert "action_items" in alert

    async def test_get_spending_alerts_specific_budget(
        self, async_client: AsyncClient, test_user, test_db
    ):
        """Test spending alerts for specific budget."""
        user_id = test_user.id

        # Create budget that covers today
        today = date.today()
        budget = Budget(
            user_id=user_id,
            name="Test Budget",
            period_start=today.replace(day=1),
            period_end=today,  # Ensure budget covers today
            allocations={"Entertainment": 100.00},
        )
        test_db.add(budget)
        await test_db.commit()
        await test_db.refresh(budget)

        # Create overspending transactions (within budget period)
        for i in range(5):
            transaction = Transaction(
                user_id=user_id,
                amount=Decimal("30.00"),
                type="EXPENSE",
                category="Entertainment",
                description=f"Entertainment {i}",
                date=today - timedelta(days=i),
                source="MANUAL",
            )
            test_db.add(transaction)
        await test_db.commit()

        response = await async_client.get(
            f"/api/advice/spending-alerts?user_id={user_id}&budget_id={budget.id}"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    async def test_get_savings_opportunities_no_data(
        self, async_client: AsyncClient, test_user, test_db
    ):
        """Test savings opportunities with no data."""
        user_id = test_user.id

        response = await async_client.get(f"/api/advice/savings-opportunities?user_id={user_id}")

        assert response.status_code == 200
        data = response.json()
        assert data == []

    async def test_get_savings_opportunities_with_high_spending(
        self, async_client: AsyncClient, test_user, test_db
    ):
        """Test savings opportunities with high spending category."""
        user_id = test_user.id

        # Create high spending in one category (>15% of total)
        for i in range(30):
            # High spending category
            transaction1 = Transaction(
                user_id=user_id,
                amount=Decimal("100.00"),
                type="EXPENSE",
                category="Dining",
                description=f"Dining {i}",
                date=date.today() - timedelta(days=i),
                source="MANUAL",
            )
            test_db.add(transaction1)

            # Lower spending in other categories
            transaction2 = Transaction(
                user_id=user_id,
                amount=Decimal("20.00"),
                type="EXPENSE",
                category="Utilities",
                description=f"Utilities {i}",
                date=date.today() - timedelta(days=i),
                source="MANUAL",
            )
            test_db.add(transaction2)

        await test_db.commit()

        response = await async_client.get(
            f"/api/advice/savings-opportunities?user_id={user_id}&lookback_months=1"
        )

        assert response.status_code == 200
        data = response.json()
        # Should identify Dining as savings opportunity
        assert len(data) >= 1

        opportunity = data[0]
        assert "Dining" in opportunity["title"]
        assert opportunity["priority"] == "MEDIUM"
        assert opportunity["category"] == "Dining"
        assert "action_items" in opportunity

    async def test_get_savings_opportunities_custom_lookback(
        self, async_client: AsyncClient, test_user, test_db
    ):
        """Test savings opportunities with custom lookback period."""
        user_id = test_user.id

        # Create transactions over 6 months
        for i in range(180):
            transaction = Transaction(
                user_id=user_id,
                amount=Decimal("50.00"),
                type="EXPENSE",
                category="Shopping",
                description=f"Shopping {i}",
                date=date.today() - timedelta(days=i),
                source="MANUAL",
            )
            test_db.add(transaction)
        await test_db.commit()

        response = await async_client.get(
            f"/api/advice/savings-opportunities?user_id={user_id}&lookback_months=6"
        )

        assert response.status_code == 200
        data = response.json()
        # Should analyze 6 months of data
        assert isinstance(data, list)

    async def test_advice_validation_max_recommendations(
        self, async_client: AsyncClient, test_user, test_db
    ):
        """Test advice with invalid max_recommendations."""
        user_id = test_user.id

        # Test too high
        response = await async_client.get(f"/api/advice?user_id={user_id}&max_recommendations=20")
        assert response.status_code == 422  # Validation error

        # Test too low
        response = await async_client.get(f"/api/advice?user_id={user_id}&max_recommendations=0")
        assert response.status_code == 422  # Validation error

    async def test_advice_validation_lookback_months(
        self, async_client: AsyncClient, test_user, test_db
    ):
        """Test savings opportunities with invalid lookback_months."""
        user_id = test_user.id

        # Test too high
        response = await async_client.get(
            f"/api/advice/savings-opportunities?user_id={user_id}&lookback_months=15"
        )
        assert response.status_code == 422  # Validation error

        # Test too low
        response = await async_client.get(
            f"/api/advice/savings-opportunities?user_id={user_id}&lookback_months=0"
        )
        assert response.status_code == 422  # Validation error

    async def test_advice_priority_ordering(self, async_client: AsyncClient, test_user, test_db):
        """Test that advice is ordered by priority."""
        user_id = test_user.id

        # Create scenario with multiple priority levels
        # High priority: overspending
        today = date.today()
        budget = Budget(
            user_id=user_id,
            name="Budget",
            period_start=today.replace(day=1),
            period_end=today,  # Ensure budget covers today
            allocations={"Food": 100.00},
        )
        test_db.add(budget)

        # Create overspending (within budget period)
        for i in range(10):
            transaction = Transaction(
                user_id=user_id,
                amount=Decimal("20.00"),
                type="EXPENSE",
                category="Food",
                description=f"Food {i}",
                date=today - timedelta(days=i),
                source="MANUAL",
            )
            test_db.add(transaction)

        await test_db.commit()

        response = await async_client.get(f"/api/advice?user_id={user_id}")

        assert response.status_code == 200
        data = response.json()

        # Check that priorities are in order
        priority_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        for i in range(len(data) - 1):
            current_priority = priority_order[data[i]["priority"]]
            next_priority = priority_order[data[i + 1]["priority"]]
            assert current_priority <= next_priority
