"""Tests for goal service."""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from app.services.goal_service import GoalService
from app.models.user import User


@pytest.fixture
async def test_user(db_session):
    """Create a test user."""
    user = User(
        id=uuid4(),
        email="goaluser@test.com",
        password_hash="hashed_password",
        first_name="Test",
        last_name="User",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def goal_service(db_session):
    """Create goal service instance."""
    return GoalService(db_session)


@pytest.mark.asyncio
class TestGoalService:
    """Test goal service functionality."""

    async def test_create_goal(self, goal_service, test_user, db_session):
        """Test creating a financial goal."""
        deadline = datetime.utcnow().date() + timedelta(days=365)

        goal = await goal_service.create_goal(
            user_id=test_user.id,
            name="Emergency Fund",
            target_amount=Decimal("10000"),
            deadline=deadline,
            category="Savings",
        )

        await db_session.commit()

        assert goal.id is not None
        assert goal.user_id == test_user.id
        assert goal.name == "Emergency Fund"
        assert goal.target_amount == Decimal("10000")
        assert goal.current_amount == Decimal("0")
        assert goal.deadline == deadline
        assert goal.category == "Savings"
        assert goal.status == "ACTIVE"

    async def test_create_goal_with_initial_amount(self, goal_service, test_user, db_session):
        """Test creating a goal with initial amount."""
        goal = await goal_service.create_goal(
            user_id=test_user.id,
            name="Vacation Fund",
            target_amount=Decimal("5000"),
            initial_amount=Decimal("1000"),
        )

        await db_session.commit()

        assert goal.current_amount == Decimal("1000")

    async def test_create_goal_invalid_target(self, goal_service, test_user):
        """Test creating a goal with invalid target amount."""
        with pytest.raises(ValueError, match="Target amount must be positive"):
            await goal_service.create_goal(
                user_id=test_user.id, name="Invalid Goal", target_amount=Decimal("0")
            )

    async def test_get_goal(self, goal_service, test_user, db_session):
        """Test getting a goal by ID."""
        goal = await goal_service.create_goal(
            user_id=test_user.id, name="Test Goal", target_amount=Decimal("1000")
        )

        await db_session.commit()

        retrieved = await goal_service.get_goal(goal.id, test_user.id)

        assert retrieved is not None
        assert retrieved.id == goal.id
        assert retrieved.name == "Test Goal"

    async def test_get_goal_wrong_user(self, goal_service, test_user, db_session):
        """Test getting a goal with wrong user ID."""
        goal = await goal_service.create_goal(
            user_id=test_user.id, name="Test Goal", target_amount=Decimal("1000")
        )

        await db_session.commit()

        # Try to get with different user ID
        retrieved = await goal_service.get_goal(goal.id, uuid4())

        assert retrieved is None

    async def test_list_goals(self, goal_service, test_user, db_session):
        """Test listing goals."""
        # Create multiple goals
        await goal_service.create_goal(
            user_id=test_user.id, name="Goal 1", target_amount=Decimal("1000")
        )

        await goal_service.create_goal(
            user_id=test_user.id, name="Goal 2", target_amount=Decimal("2000")
        )

        await db_session.commit()

        goals = await goal_service.list_goals(test_user.id)

        assert len(goals) == 2
        assert all(g.user_id == test_user.id for g in goals)

    async def test_list_goals_by_status(self, goal_service, test_user, db_session):
        """Test listing goals filtered by status."""
        # Create active goal
        await goal_service.create_goal(
            user_id=test_user.id, name="Active Goal", target_amount=Decimal("1000")
        )

        # Create achieved goal
        achieved_goal = await goal_service.create_goal(
            user_id=test_user.id,
            name="Achieved Goal",
            target_amount=Decimal("1000"),
            initial_amount=Decimal("1000"),
        )
        achieved_goal.status = "ACHIEVED"

        await db_session.commit()

        active_goals = await goal_service.list_goals(test_user.id, status="ACTIVE")
        achieved_goals = await goal_service.list_goals(test_user.id, status="ACHIEVED")

        assert len(active_goals) == 1
        assert len(achieved_goals) == 1
        assert active_goals[0].name == "Active Goal"
        assert achieved_goals[0].name == "Achieved Goal"

    async def test_get_goal_progress(self, goal_service, test_user, db_session):
        """Test getting goal progress."""
        goal = await goal_service.create_goal(
            user_id=test_user.id,
            name="Test Goal",
            target_amount=Decimal("1000"),
            initial_amount=Decimal("250"),
        )

        await db_session.commit()

        progress = await goal_service.get_goal_progress(test_user.id, goal.id)

        assert progress is not None
        assert progress.goal_id == goal.id
        assert progress.target_amount == Decimal("1000")
        assert progress.current_amount == Decimal("250")
        assert progress.progress_percent == 25.0
        assert progress.remaining_amount == Decimal("750")

    async def test_update_goal_progress(self, goal_service, test_user, db_session):
        """Test updating goal progress."""
        goal = await goal_service.create_goal(
            user_id=test_user.id, name="Test Goal", target_amount=Decimal("1000")
        )

        await db_session.commit()

        # Update progress
        updated = await goal_service.update_goal_progress(goal.id, test_user.id, Decimal("250"))

        assert updated is not None
        assert updated.current_amount == Decimal("250")
        assert updated.status == "ACTIVE"

    async def test_goal_achievement_detection(self, goal_service, test_user, db_session):
        """Test automatic goal achievement detection."""
        goal = await goal_service.create_goal(
            user_id=test_user.id,
            name="Test Goal",
            target_amount=Decimal("1000"),
            initial_amount=Decimal("900"),
        )

        await db_session.commit()

        # Update progress to reach target
        updated = await goal_service.update_goal_progress(goal.id, test_user.id, Decimal("100"))

        assert updated is not None
        assert updated.current_amount == Decimal("1000")
        assert updated.status == "ACHIEVED"

    async def test_update_goal_progress_from_transaction(self, goal_service, test_user, db_session):
        """Test auto-updating goals from transaction."""
        # Create goal with category
        goal = await goal_service.create_goal(
            user_id=test_user.id,
            name="Savings Goal",
            target_amount=Decimal("5000"),
            category="Savings",
        )

        await db_session.commit()

        # Simulate transaction in same category
        updated_goals = await goal_service.update_goal_progress_from_transaction(
            user_id=test_user.id, transaction_amount=Decimal("500"), transaction_category="Savings"
        )

        assert len(updated_goals) == 1
        assert updated_goals[0].id == goal.id
        assert updated_goals[0].current_amount == Decimal("500")

    async def test_update_goal_progress_no_matching_category(
        self, goal_service, test_user, db_session
    ):
        """Test that goals don't update for non-matching categories."""
        # Create goal with category
        await goal_service.create_goal(
            user_id=test_user.id,
            name="Savings Goal",
            target_amount=Decimal("5000"),
            category="Savings",
        )

        await db_session.commit()

        # Simulate transaction in different category
        updated_goals = await goal_service.update_goal_progress_from_transaction(
            user_id=test_user.id,
            transaction_amount=Decimal("500"),
            transaction_category="Groceries",
        )

        assert len(updated_goals) == 0

    async def test_goal_risk_detection(self, goal_service, test_user, db_session):
        """Test goal risk detection."""
        # Create goal with near deadline and low progress
        deadline = datetime.utcnow().date() + timedelta(days=30)

        goal = await goal_service.create_goal(
            user_id=test_user.id,
            name="Urgent Goal",
            target_amount=Decimal("10000"),
            initial_amount=Decimal("1000"),
            deadline=deadline,
        )

        # Backdate creation to simulate slow progress
        goal.created_at = datetime.utcnow() - timedelta(days=300)

        await db_session.commit()

        # Check for risks
        alerts = await goal_service.check_goal_risks(test_user.id)

        # Should have at least one alert
        assert len(alerts) > 0
        urgent_alert = next((a for a in alerts if a.goal_id == goal.id), None)
        assert urgent_alert is not None
        assert urgent_alert.severity in ["WARNING", "CRITICAL"]

    async def test_goal_no_risk_on_track(self, goal_service, test_user, db_session):
        """Test that on-track goals don't generate risk alerts."""
        # Create goal with good progress
        deadline = datetime.utcnow().date() + timedelta(days=365)

        await goal_service.create_goal(
            user_id=test_user.id,
            name="On Track Goal",
            target_amount=Decimal("1000"),
            initial_amount=Decimal("900"),
            deadline=deadline,
        )

        await db_session.commit()

        # Check for risks
        alerts = await goal_service.check_goal_risks(test_user.id)

        # Should have no alerts for this goal
        assert len(alerts) == 0

    async def test_update_goal(self, goal_service, test_user, db_session):
        """Test updating a goal."""
        goal = await goal_service.create_goal(
            user_id=test_user.id, name="Original Name", target_amount=Decimal("1000")
        )

        await db_session.commit()

        # Update goal
        updated = await goal_service.update_goal(
            goal.id, test_user.id, name="Updated Name", target_amount=Decimal("2000")
        )

        assert updated is not None
        assert updated.name == "Updated Name"
        assert updated.target_amount == Decimal("2000")

    async def test_delete_goal(self, goal_service, test_user, db_session):
        """Test deleting a goal."""
        goal = await goal_service.create_goal(
            user_id=test_user.id, name="Test Goal", target_amount=Decimal("1000")
        )

        await db_session.commit()

        # Delete goal
        result = await goal_service.delete_goal(goal.id, test_user.id)

        assert result is True

        # Verify goal is deleted
        retrieved = await goal_service.get_goal(goal.id, test_user.id)
        assert retrieved is None

    async def test_delete_nonexistent_goal(self, goal_service, test_user):
        """Test deleting a nonexistent goal."""
        result = await goal_service.delete_goal(uuid4(), test_user.id)

        assert result is False
