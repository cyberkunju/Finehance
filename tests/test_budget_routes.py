"""Tests for budget API endpoints."""

import pytest
from datetime import datetime, timedelta, date
from decimal import Decimal
from httpx import AsyncClient
from uuid import uuid4

from app.models.budget import Budget
from app.models.transaction import Transaction
from app.schemas.transaction import TransactionType, TransactionSource


@pytest.mark.asyncio
class TestBudgetRoutes:
    """Test budget API endpoints."""
    
    async def test_create_budget_success(self, async_client: AsyncClient, test_user, test_db):
        """Test successful budget creation."""
        user_id = test_user.id
        
        response = await async_client.post(
            f"/api/budgets?user_id={user_id}",
            json={
                "name": "Monthly Budget",
                "period_start": "2024-01-01",
                "period_end": "2024-01-31",
                "allocations": {
                    "Groceries": "500.00",
                    "Dining": "200.00",
                    "Transportation": "150.00"
                }
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Monthly Budget"
        assert data["period_start"] == "2024-01-01"
        assert data["period_end"] == "2024-01-31"
        assert "Groceries" in data["allocations"]
        assert data["allocations"]["Groceries"] == 500.0
        assert "id" in data
    
    async def test_create_budget_invalid_period(self, async_client: AsyncClient, test_user, test_db):
        """Test budget creation with invalid period."""
        user_id = test_user.id
        
        response = await async_client.post(
            f"/api/budgets?user_id={user_id}",
            json={
                "name": "Invalid Budget",
                "period_start": "2024-01-31",
                "period_end": "2024-01-01",
                "allocations": {
                    "Groceries": "500.00"
                }
            }
        )
        
        assert response.status_code == 422  # Validation error
    
    async def test_create_budget_negative_allocation(self, async_client: AsyncClient, test_user, test_db):
        """Test budget creation with negative allocation."""
        user_id = test_user.id
        
        response = await async_client.post(
            f"/api/budgets?user_id={user_id}",
            json={
                "name": "Invalid Budget",
                "period_start": "2024-01-01",
                "period_end": "2024-01-31",
                "allocations": {
                    "Groceries": "-500.00"
                }
            }
        )
        
        assert response.status_code == 422  # Validation error
    
    async def test_list_budgets_empty(self, async_client: AsyncClient, test_user, test_db):
        """Test listing budgets when none exist."""
        user_id = test_user.id
        
        response = await async_client.get(f"/api/budgets?user_id={user_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data == []
    
    async def test_list_budgets_with_data(self, async_client: AsyncClient, test_user, test_db):
        """Test listing budgets with data."""
        user_id = test_user.id
        
        # Create test budgets
        for i in range(3):
            budget = Budget(
                user_id=user_id,
                name=f"Budget {i}",
                period_start=date(2024, i+1, 1),
                period_end=date(2024, i+1, 28),
                allocations={"Groceries": 500.0}
            )
            test_db.add(budget)
        await test_db.commit()
        
        response = await async_client.get(f"/api/budgets?user_id={user_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
    
    async def test_list_budgets_active_only(self, async_client: AsyncClient, test_user, test_db):
        """Test listing only active budgets."""
        user_id = test_user.id
        today = datetime.utcnow().date()
        
        # Create past budget
        past_budget = Budget(
            user_id=user_id,
            name="Past Budget",
            period_start=today - timedelta(days=60),
            period_end=today - timedelta(days=30),
            allocations={"Groceries": 500.0}
        )
        test_db.add(past_budget)
        
        # Create active budget
        active_budget = Budget(
            user_id=user_id,
            name="Active Budget",
            period_start=today - timedelta(days=15),
            period_end=today + timedelta(days=15),
            allocations={"Groceries": 500.0}
        )
        test_db.add(active_budget)
        
        await test_db.commit()
        
        response = await async_client.get(f"/api/budgets?user_id={user_id}&active_only=true")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Active Budget"
    
    async def test_get_budget_success(self, async_client: AsyncClient, test_user, test_db):
        """Test getting a single budget."""
        user_id = test_user.id
        
        # Create budget
        budget = Budget(
            user_id=user_id,
            name="Test Budget",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 1, 31),
            allocations={"Groceries": 500.0}
        )
        test_db.add(budget)
        await test_db.commit()
        await test_db.refresh(budget)
        
        response = await async_client.get(f"/api/budgets/{budget.id}?user_id={user_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(budget.id)
        assert data["name"] == "Test Budget"
    
    async def test_get_budget_not_found(self, async_client: AsyncClient, test_user, test_db):
        """Test getting a non-existent budget."""
        user_id = test_user.id
        fake_id = uuid4()
        
        response = await async_client.get(f"/api/budgets/{fake_id}?user_id={user_id}")
        
        assert response.status_code == 404
    
    async def test_get_budget_progress(self, async_client: AsyncClient, test_user, test_db):
        """Test getting budget progress."""
        user_id = test_user.id
        
        # Create budget
        budget = Budget(
            user_id=user_id,
            name="Test Budget",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 1, 31),
            allocations={"Groceries": 500.0, "Dining": 200.0}
        )
        test_db.add(budget)
        await test_db.commit()
        await test_db.refresh(budget)
        
        # Create transactions
        transaction1 = Transaction(
            user_id=user_id,
            amount=Decimal("300.00"),
            date=date(2024, 1, 15),
            description="Grocery shopping",
            category="Groceries",
            type="EXPENSE",
            source="MANUAL"
        )
        transaction2 = Transaction(
            user_id=user_id,
            amount=Decimal("50.00"),
            date=date(2024, 1, 16),
            description="Restaurant",
            category="Dining",
            type="EXPENSE",
            source="MANUAL"
        )
        test_db.add(transaction1)
        test_db.add(transaction2)
        await test_db.commit()
        
        response = await async_client.get(f"/api/budgets/{budget.id}/progress?user_id={user_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert "progress" in data
        assert "alerts" in data
        assert "Groceries" in data["progress"]
        assert data["progress"]["Groceries"]["spent"] == "300.00"
        assert data["progress"]["Groceries"]["remaining"] == "200.00"
    
    async def test_get_budget_progress_with_alerts(self, async_client: AsyncClient, test_user, test_db):
        """Test getting budget progress with overspending alerts."""
        user_id = test_user.id
        
        # Create budget
        budget = Budget(
            user_id=user_id,
            name="Test Budget",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 1, 31),
            allocations={"Groceries": 100.0}
        )
        test_db.add(budget)
        await test_db.commit()
        await test_db.refresh(budget)
        
        # Create transaction that exceeds budget
        transaction = Transaction(
            user_id=user_id,
            amount=Decimal("120.00"),
            date=date(2024, 1, 15),
            description="Grocery shopping",
            category="Groceries",
            type="EXPENSE",
            source="MANUAL"
        )
        test_db.add(transaction)
        await test_db.commit()
        
        response = await async_client.get(f"/api/budgets/{budget.id}/progress?user_id={user_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["alerts"]) > 0
        assert data["alerts"][0]["severity"] == "CRITICAL"
        assert data["alerts"][0]["category"] == "Groceries"
    
    async def test_update_budget_success(self, async_client: AsyncClient, test_user, test_db):
        """Test updating a budget."""
        user_id = test_user.id
        
        # Create budget
        budget = Budget(
            user_id=user_id,
            name="Original Name",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 1, 31),
            allocations={"Groceries": 500.0}
        )
        test_db.add(budget)
        await test_db.commit()
        await test_db.refresh(budget)
        
        # Update budget
        response = await async_client.put(
            f"/api/budgets/{budget.id}?user_id={user_id}",
            json={
                "name": "Updated Name",
                "allocations": {
                    "Groceries": "600.00",
                    "Dining": "200.00"
                }
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["allocations"]["Groceries"] == 600.0
        assert "Dining" in data["allocations"]
    
    async def test_update_budget_partial(self, async_client: AsyncClient, test_user, test_db):
        """Test partial update of a budget."""
        user_id = test_user.id
        
        # Create budget
        budget = Budget(
            user_id=user_id,
            name="Original Name",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 1, 31),
            allocations={"Groceries": 500.0}
        )
        test_db.add(budget)
        await test_db.commit()
        await test_db.refresh(budget)
        
        # Update only name
        response = await async_client.put(
            f"/api/budgets/{budget.id}?user_id={user_id}",
            json={"name": "Updated Name"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["allocations"]["Groceries"] == 500.0  # Unchanged
    
    async def test_update_budget_not_found(self, async_client: AsyncClient, test_user, test_db):
        """Test updating a non-existent budget."""
        user_id = test_user.id
        fake_id = uuid4()
        
        response = await async_client.put(
            f"/api/budgets/{fake_id}?user_id={user_id}",
            json={"name": "Updated"}
        )
        
        assert response.status_code == 404
    
    async def test_update_budget_no_updates(self, async_client: AsyncClient, test_user, test_db):
        """Test updating a budget with no changes."""
        user_id = test_user.id
        
        # Create budget
        budget = Budget(
            user_id=user_id,
            name="Test Budget",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 1, 31),
            allocations={"Groceries": 500.0}
        )
        test_db.add(budget)
        await test_db.commit()
        await test_db.refresh(budget)
        
        # Update with empty dict
        response = await async_client.put(
            f"/api/budgets/{budget.id}?user_id={user_id}",
            json={}
        )
        
        assert response.status_code == 400
    
    async def test_delete_budget_success(self, async_client: AsyncClient, test_user, test_db):
        """Test deleting a budget."""
        user_id = test_user.id
        
        # Create budget
        budget = Budget(
            user_id=user_id,
            name="To be deleted",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 1, 31),
            allocations={"Groceries": 500.0}
        )
        test_db.add(budget)
        await test_db.commit()
        await test_db.refresh(budget)
        
        # Delete budget
        response = await async_client.delete(f"/api/budgets/{budget.id}?user_id={user_id}")
        
        assert response.status_code == 204
        
        # Verify deletion
        get_response = await async_client.get(f"/api/budgets/{budget.id}?user_id={user_id}")
        assert get_response.status_code == 404
    
    async def test_delete_budget_not_found(self, async_client: AsyncClient, test_user, test_db):
        """Test deleting a non-existent budget."""
        user_id = test_user.id
        fake_id = uuid4()
        
        response = await async_client.delete(f"/api/budgets/{fake_id}?user_id={user_id}")
        
        assert response.status_code == 404
    
    async def test_get_optimization_suggestions(self, async_client: AsyncClient, test_user, test_db):
        """Test getting budget optimization suggestions."""
        user_id = test_user.id
        
        # Create budget
        budget = Budget(
            user_id=user_id,
            name="Test Budget",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 1, 31),
            allocations={"Groceries": 500.0, "Dining": 200.0}
        )
        test_db.add(budget)
        await test_db.commit()
        await test_db.refresh(budget)
        
        # Create transactions showing overspending in Groceries
        for i in range(5):
            transaction = Transaction(
                user_id=user_id,
                amount=Decimal("150.00"),
                date=date(2024, 1, 10 + i),
                description=f"Grocery shopping {i}",
                category="Groceries",
                type="EXPENSE",
                source="MANUAL"
            )
            test_db.add(transaction)
        await test_db.commit()
        
        response = await async_client.post(
            f"/api/budgets/{budget.id}/optimize?user_id={user_id}&historical_months=1"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "suggestions" in data
        # May or may not have suggestions depending on spending patterns
    
    async def test_apply_optimization_without_approval(self, async_client: AsyncClient, test_user, test_db):
        """Test applying optimization without user approval."""
        user_id = test_user.id
        
        # Create budget
        budget = Budget(
            user_id=user_id,
            name="Test Budget",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 1, 31),
            allocations={"Groceries": 500.0}
        )
        test_db.add(budget)
        await test_db.commit()
        await test_db.refresh(budget)
        
        response = await async_client.put(
            f"/api/budgets/{budget.id}/apply-optimization?user_id={user_id}",
            json={
                "suggestions": [],
                "user_approved": False
            }
        )
        
        assert response.status_code == 400
        assert "approval required" in response.json()["detail"].lower()
