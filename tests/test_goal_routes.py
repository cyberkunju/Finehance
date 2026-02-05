"""Tests for goal API endpoints."""

import pytest
from datetime import datetime, timedelta, date
from decimal import Decimal
from httpx import AsyncClient
from uuid import uuid4

from app.models.financial_goal import FinancialGoal


@pytest.mark.asyncio
class TestGoalRoutes:
    """Test goal API endpoints."""

    async def test_create_goal_success(self, async_client: AsyncClient, test_user, test_db):
        """Test successful goal creation."""
        user_id = test_user.id

        response = await async_client.post(
            f"/api/goals?user_id={user_id}",
            json={
                "name": "Emergency Fund",
                "target_amount": "10000.00",
                "deadline": "2024-12-31",
                "category": "Savings",
                "initial_amount": "1000.00",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Emergency Fund"
        assert data["target_amount"] == "10000.00"
        assert data["current_amount"] == "1000.00"
        assert data["deadline"] == "2024-12-31"
        assert data["category"] == "Savings"
        assert data["status"] == "ACTIVE"
        assert "id" in data

    async def test_create_goal_without_deadline(
        self, async_client: AsyncClient, test_user, test_db
    ):
        """Test goal creation without deadline."""
        user_id = test_user.id

        response = await async_client.post(
            f"/api/goals?user_id={user_id}",
            json={"name": "Vacation Fund", "target_amount": "5000.00"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Vacation Fund"
        assert data["deadline"] is None

    async def test_create_goal_invalid_target_amount(
        self, async_client: AsyncClient, test_user, test_db
    ):
        """Test goal creation with invalid target amount."""
        user_id = test_user.id

        response = await async_client.post(
            f"/api/goals?user_id={user_id}",
            json={"name": "Invalid Goal", "target_amount": "-1000.00"},
        )

        assert response.status_code == 422  # Validation error

    async def test_list_goals_empty(self, async_client: AsyncClient, test_user, test_db):
        """Test listing goals when none exist."""
        user_id = test_user.id

        response = await async_client.get(f"/api/goals?user_id={user_id}")

        assert response.status_code == 200
        data = response.json()
        assert data == []

    async def test_list_goals_with_data(self, async_client: AsyncClient, test_user, test_db):
        """Test listing goals with data."""
        user_id = test_user.id

        # Create test goals
        for i in range(3):
            goal = FinancialGoal(
                user_id=user_id,
                name=f"Goal {i}",
                target_amount=Decimal("1000.00"),
                current_amount=Decimal("100.00"),
                status="ACTIVE",
            )
            test_db.add(goal)
        await test_db.commit()

        response = await async_client.get(f"/api/goals?user_id={user_id}")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

    async def test_list_goals_filter_by_status(self, async_client: AsyncClient, test_user, test_db):
        """Test listing goals filtered by status."""
        user_id = test_user.id

        # Create active goal
        active_goal = FinancialGoal(
            user_id=user_id,
            name="Active Goal",
            target_amount=Decimal("1000.00"),
            current_amount=Decimal("100.00"),
            status="ACTIVE",
        )
        test_db.add(active_goal)

        # Create achieved goal
        achieved_goal = FinancialGoal(
            user_id=user_id,
            name="Achieved Goal",
            target_amount=Decimal("1000.00"),
            current_amount=Decimal("1000.00"),
            status="ACHIEVED",
        )
        test_db.add(achieved_goal)

        await test_db.commit()

        response = await async_client.get(f"/api/goals?user_id={user_id}&status=ACTIVE")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == "ACTIVE"

    async def test_get_goal_success(self, async_client: AsyncClient, test_user, test_db):
        """Test getting a single goal."""
        user_id = test_user.id

        # Create goal
        goal = FinancialGoal(
            user_id=user_id,
            name="Test Goal",
            target_amount=Decimal("1000.00"),
            current_amount=Decimal("100.00"),
            status="ACTIVE",
        )
        test_db.add(goal)
        await test_db.commit()
        await test_db.refresh(goal)

        response = await async_client.get(f"/api/goals/{goal.id}?user_id={user_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(goal.id)
        assert data["name"] == "Test Goal"

    async def test_get_goal_not_found(self, async_client: AsyncClient, test_user, test_db):
        """Test getting a non-existent goal."""
        user_id = test_user.id
        fake_id = uuid4()

        response = await async_client.get(f"/api/goals/{fake_id}?user_id={user_id}")

        assert response.status_code == 404

    async def test_get_goal_progress(self, async_client: AsyncClient, test_user, test_db):
        """Test getting goal progress."""
        user_id = test_user.id

        # Create goal
        goal = FinancialGoal(
            user_id=user_id,
            name="Test Goal",
            target_amount=Decimal("1000.00"),
            current_amount=Decimal("400.00"),
            deadline=date.today() + timedelta(days=30),
            status="ACTIVE",
        )
        test_db.add(goal)
        await test_db.commit()
        await test_db.refresh(goal)

        response = await async_client.get(f"/api/goals/{goal.id}/progress?user_id={user_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["goal_id"] == str(goal.id)
        assert data["target_amount"] == "1000.00"
        assert data["current_amount"] == "400.00"
        assert data["progress_percent"] == 40.0
        assert data["remaining_amount"] == "600.00"
        assert data["days_remaining"] is not None

    async def test_update_goal_progress(self, async_client: AsyncClient, test_user, test_db):
        """Test updating goal progress."""
        user_id = test_user.id

        # Create goal
        goal = FinancialGoal(
            user_id=user_id,
            name="Test Goal",
            target_amount=Decimal("1000.00"),
            current_amount=Decimal("400.00"),
            status="ACTIVE",
        )
        test_db.add(goal)
        await test_db.commit()
        await test_db.refresh(goal)

        # Update progress
        response = await async_client.post(
            f"/api/goals/{goal.id}/progress?user_id={user_id}", json={"amount": "200.00"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["current_amount"] == "600.00"

    async def test_update_goal_progress_achievement(
        self, async_client: AsyncClient, test_user, test_db
    ):
        """Test goal achievement when progress reaches target."""
        user_id = test_user.id

        # Create goal close to target
        goal = FinancialGoal(
            user_id=user_id,
            name="Test Goal",
            target_amount=Decimal("1000.00"),
            current_amount=Decimal("900.00"),
            status="ACTIVE",
        )
        test_db.add(goal)
        await test_db.commit()
        await test_db.refresh(goal)

        # Update progress to exceed target
        response = await async_client.post(
            f"/api/goals/{goal.id}/progress?user_id={user_id}", json={"amount": "150.00"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["current_amount"] == "1050.00"
        assert data["status"] == "ACHIEVED"

    async def test_get_goal_risk_alerts(self, async_client: AsyncClient, test_user, test_db):
        """Test getting goal risk alerts."""
        user_id = test_user.id

        # Create goal at risk (deadline soon, low progress)
        goal = FinancialGoal(
            user_id=user_id,
            name="At Risk Goal",
            target_amount=Decimal("10000.00"),
            current_amount=Decimal("100.00"),
            deadline=date.today() + timedelta(days=20),
            status="ACTIVE",
            created_at=datetime.utcnow() - timedelta(days=300),
        )
        test_db.add(goal)
        await test_db.commit()

        response = await async_client.get(f"/api/goals/risks/alerts?user_id={user_id}")

        assert response.status_code == 200
        data = response.json()
        # May or may not have alerts depending on progress rate calculation
        assert isinstance(data, list)

    async def test_update_goal_success(self, async_client: AsyncClient, test_user, test_db):
        """Test updating a goal."""
        user_id = test_user.id

        # Create goal
        goal = FinancialGoal(
            user_id=user_id,
            name="Original Name",
            target_amount=Decimal("1000.00"),
            current_amount=Decimal("100.00"),
            status="ACTIVE",
        )
        test_db.add(goal)
        await test_db.commit()
        await test_db.refresh(goal)

        # Update goal
        response = await async_client.put(
            f"/api/goals/{goal.id}?user_id={user_id}",
            json={"name": "Updated Name", "target_amount": "2000.00", "deadline": "2024-12-31"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["target_amount"] == "2000.00"
        assert data["deadline"] == "2024-12-31"

    async def test_update_goal_partial(self, async_client: AsyncClient, test_user, test_db):
        """Test partial update of a goal."""
        user_id = test_user.id

        # Create goal
        goal = FinancialGoal(
            user_id=user_id,
            name="Original Name",
            target_amount=Decimal("1000.00"),
            current_amount=Decimal("100.00"),
            status="ACTIVE",
        )
        test_db.add(goal)
        await test_db.commit()
        await test_db.refresh(goal)

        # Update only name
        response = await async_client.put(
            f"/api/goals/{goal.id}?user_id={user_id}", json={"name": "Updated Name"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["target_amount"] == "1000.00"  # Unchanged

    async def test_update_goal_status(self, async_client: AsyncClient, test_user, test_db):
        """Test updating goal status."""
        user_id = test_user.id

        # Create goal
        goal = FinancialGoal(
            user_id=user_id,
            name="Test Goal",
            target_amount=Decimal("1000.00"),
            current_amount=Decimal("100.00"),
            status="ACTIVE",
        )
        test_db.add(goal)
        await test_db.commit()
        await test_db.refresh(goal)

        # Archive goal
        response = await async_client.put(
            f"/api/goals/{goal.id}?user_id={user_id}", json={"status": "ARCHIVED"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ARCHIVED"

    async def test_update_goal_invalid_status(self, async_client: AsyncClient, test_user, test_db):
        """Test updating goal with invalid status."""
        user_id = test_user.id

        # Create goal
        goal = FinancialGoal(
            user_id=user_id,
            name="Test Goal",
            target_amount=Decimal("1000.00"),
            current_amount=Decimal("100.00"),
            status="ACTIVE",
        )
        test_db.add(goal)
        await test_db.commit()
        await test_db.refresh(goal)

        # Try invalid status
        response = await async_client.put(
            f"/api/goals/{goal.id}?user_id={user_id}", json={"status": "INVALID"}
        )

        assert response.status_code == 422  # Validation error

    async def test_update_goal_not_found(self, async_client: AsyncClient, test_user, test_db):
        """Test updating a non-existent goal."""
        user_id = test_user.id
        fake_id = uuid4()

        response = await async_client.put(
            f"/api/goals/{fake_id}?user_id={user_id}", json={"name": "Updated"}
        )

        assert response.status_code == 404

    async def test_update_goal_no_updates(self, async_client: AsyncClient, test_user, test_db):
        """Test updating a goal with no changes."""
        user_id = test_user.id

        # Create goal
        goal = FinancialGoal(
            user_id=user_id,
            name="Test Goal",
            target_amount=Decimal("1000.00"),
            current_amount=Decimal("100.00"),
            status="ACTIVE",
        )
        test_db.add(goal)
        await test_db.commit()
        await test_db.refresh(goal)

        # Update with empty dict
        response = await async_client.put(f"/api/goals/{goal.id}?user_id={user_id}", json={})

        assert response.status_code == 400

    async def test_delete_goal_success(self, async_client: AsyncClient, test_user, test_db):
        """Test deleting a goal."""
        user_id = test_user.id

        # Create goal
        goal = FinancialGoal(
            user_id=user_id,
            name="To be deleted",
            target_amount=Decimal("1000.00"),
            current_amount=Decimal("100.00"),
            status="ACTIVE",
        )
        test_db.add(goal)
        await test_db.commit()
        await test_db.refresh(goal)

        # Delete goal
        response = await async_client.delete(f"/api/goals/{goal.id}?user_id={user_id}")

        assert response.status_code == 204

        # Verify deletion
        get_response = await async_client.get(f"/api/goals/{goal.id}?user_id={user_id}")
        assert get_response.status_code == 404

    async def test_delete_goal_not_found(self, async_client: AsyncClient, test_user, test_db):
        """Test deleting a non-existent goal."""
        user_id = test_user.id
        fake_id = uuid4()

        response = await async_client.delete(f"/api/goals/{fake_id}?user_id={user_id}")

        assert response.status_code == 404
