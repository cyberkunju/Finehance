"""Tests for ML Model Service."""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.ml_model_service import MLModelService


@pytest.fixture
def ml_model_service(db_session: AsyncSession) -> MLModelService:
    """Create ML model service instance."""
    return MLModelService(db_session)


class TestCreateModelVersion:
    """Tests for creating model versions."""

    async def test_create_model_version_success(
        self,
        ml_model_service: MLModelService,
        db_session: AsyncSession,
    ):
        """Test successful model version creation."""
        model = await ml_model_service.create_model_version(
            model_type="CATEGORIZATION",
            version="1.0.0",
            model_path="/models/categorization_v1.pkl",
            accuracy=0.85,
            precision=0.82,
            recall=0.88,
        )
        await db_session.commit()

        assert model.id is not None
        assert model.model_type == "CATEGORIZATION"
        assert model.version == "1.0.0"
        assert model.accuracy == 0.85
        assert model.precision == 0.82
        assert model.recall == 0.88
        assert model.user_id is None  # Global model
        assert model.is_active is False
        assert model.trained_at is not None

    async def test_create_user_specific_model(
        self,
        ml_model_service: MLModelService,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test creating user-specific model."""
        model = await ml_model_service.create_model_version(
            model_type="CATEGORIZATION",
            version="1.0.0",
            model_path="/models/user_model.pkl",
            user_id=test_user.id,
            accuracy=0.90,
        )
        await db_session.commit()

        assert model.user_id == test_user.id
        assert model.accuracy == 0.90

    async def test_create_active_model(
        self,
        ml_model_service: MLModelService,
        db_session: AsyncSession,
    ):
        """Test creating model with is_active=True."""
        model = await ml_model_service.create_model_version(
            model_type="PREDICTION",
            version="2.0.0",
            model_path="/models/prediction_v2.pkl",
            is_active=True,
        )
        await db_session.commit()

        assert model.is_active is True

    async def test_create_model_invalid_type(
        self,
        ml_model_service: MLModelService,
    ):
        """Test creating model with invalid type raises error."""
        with pytest.raises(ValueError, match="Invalid model_type"):
            await ml_model_service.create_model_version(
                model_type="INVALID",
                version="1.0.0",
                model_path="/models/invalid.pkl",
            )

    async def test_create_model_invalid_accuracy(
        self,
        ml_model_service: MLModelService,
    ):
        """Test creating model with invalid accuracy raises error."""
        with pytest.raises(ValueError, match="accuracy must be between 0 and 1"):
            await ml_model_service.create_model_version(
                model_type="CATEGORIZATION",
                version="1.0.0",
                model_path="/models/model.pkl",
                accuracy=1.5,
            )

    async def test_create_model_invalid_precision(
        self,
        ml_model_service: MLModelService,
    ):
        """Test creating model with invalid precision raises error."""
        with pytest.raises(ValueError, match="precision must be between 0 and 1"):
            await ml_model_service.create_model_version(
                model_type="CATEGORIZATION",
                version="1.0.0",
                model_path="/models/model.pkl",
                precision=-0.1,
            )


class TestGetModelVersion:
    """Tests for retrieving model versions."""

    async def test_get_existing_model(
        self,
        ml_model_service: MLModelService,
        db_session: AsyncSession,
    ):
        """Test retrieving existing model version."""
        created = await ml_model_service.create_model_version(
            model_type="CATEGORIZATION",
            version="1.0.0",
            model_path="/models/model.pkl",
        )
        await db_session.commit()

        retrieved = await ml_model_service.get_model_version(created.id)
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.version == "1.0.0"

    async def test_get_nonexistent_model(
        self,
        ml_model_service: MLModelService,
    ):
        """Test retrieving nonexistent model returns None."""
        result = await ml_model_service.get_model_version(uuid4())
        assert result is None


class TestGetActiveModel:
    """Tests for retrieving active models."""

    async def test_get_active_global_model(
        self,
        ml_model_service: MLModelService,
        db_session: AsyncSession,
    ):
        """Test retrieving active global model."""
        # Create inactive model
        await ml_model_service.create_model_version(
            model_type="CATEGORIZATION",
            version="1.0.0",
            model_path="/models/v1.pkl",
            is_active=False,
        )

        # Create active model
        active = await ml_model_service.create_model_version(
            model_type="CATEGORIZATION",
            version="2.0.0",
            model_path="/models/v2.pkl",
            is_active=True,
        )
        await db_session.commit()

        retrieved = await ml_model_service.get_active_model("CATEGORIZATION")
        assert retrieved is not None
        assert retrieved.id == active.id
        assert retrieved.version == "2.0.0"

    async def test_get_active_user_model(
        self,
        ml_model_service: MLModelService,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test retrieving active user-specific model."""
        active = await ml_model_service.create_model_version(
            model_type="CATEGORIZATION",
            version="1.0.0",
            model_path="/models/user_model.pkl",
            user_id=test_user.id,
            is_active=True,
        )
        await db_session.commit()

        retrieved = await ml_model_service.get_active_model(
            "CATEGORIZATION",
            user_id=test_user.id,
        )
        assert retrieved is not None
        assert retrieved.id == active.id
        assert retrieved.user_id == test_user.id

    async def test_get_active_model_none_active(
        self,
        ml_model_service: MLModelService,
        db_session: AsyncSession,
    ):
        """Test retrieving active model when none are active."""
        await ml_model_service.create_model_version(
            model_type="CATEGORIZATION",
            version="1.0.0",
            model_path="/models/v1.pkl",
            is_active=False,
        )
        await db_session.commit()

        result = await ml_model_service.get_active_model("CATEGORIZATION")
        assert result is None


class TestListModelVersions:
    """Tests for listing model versions."""

    async def test_list_all_models(
        self,
        ml_model_service: MLModelService,
        db_session: AsyncSession,
    ):
        """Test listing all model versions."""
        await ml_model_service.create_model_version(
            model_type="CATEGORIZATION",
            version="1.0.0",
            model_path="/models/v1.pkl",
        )
        await ml_model_service.create_model_version(
            model_type="PREDICTION",
            version="1.0.0",
            model_path="/models/pred_v1.pkl",
        )
        await db_session.commit()

        models = await ml_model_service.list_model_versions()
        assert len(models) == 2

    async def test_list_models_by_type(
        self,
        ml_model_service: MLModelService,
        db_session: AsyncSession,
    ):
        """Test listing models filtered by type."""
        await ml_model_service.create_model_version(
            model_type="CATEGORIZATION",
            version="1.0.0",
            model_path="/models/cat_v1.pkl",
        )
        await ml_model_service.create_model_version(
            model_type="PREDICTION",
            version="1.0.0",
            model_path="/models/pred_v1.pkl",
        )
        await db_session.commit()

        models = await ml_model_service.list_model_versions(model_type="CATEGORIZATION")
        assert len(models) == 1
        assert models[0].model_type == "CATEGORIZATION"

    async def test_list_models_by_user(
        self,
        ml_model_service: MLModelService,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test listing models filtered by user."""
        await ml_model_service.create_model_version(
            model_type="CATEGORIZATION",
            version="1.0.0",
            model_path="/models/global.pkl",
        )
        await ml_model_service.create_model_version(
            model_type="CATEGORIZATION",
            version="1.0.0",
            model_path="/models/user.pkl",
            user_id=test_user.id,
        )
        await db_session.commit()

        models = await ml_model_service.list_model_versions(user_id=test_user.id)
        assert len(models) == 1
        assert models[0].user_id == test_user.id

    async def test_list_models_by_active_status(
        self,
        ml_model_service: MLModelService,
        db_session: AsyncSession,
    ):
        """Test listing models filtered by active status."""
        await ml_model_service.create_model_version(
            model_type="CATEGORIZATION",
            version="1.0.0",
            model_path="/models/v1.pkl",
            is_active=True,
        )
        await ml_model_service.create_model_version(
            model_type="CATEGORIZATION",
            version="2.0.0",
            model_path="/models/v2.pkl",
            is_active=False,
        )
        await db_session.commit()

        active_models = await ml_model_service.list_model_versions(is_active=True)
        assert len(active_models) == 1
        assert active_models[0].is_active is True

    async def test_list_models_ordered_by_date(
        self,
        ml_model_service: MLModelService,
        db_session: AsyncSession,
    ):
        """Test that models are ordered by trained_at descending."""
        model1 = await ml_model_service.create_model_version(
            model_type="CATEGORIZATION",
            version="1.0.0",
            model_path="/models/v1.pkl",
        )
        model1.trained_at = datetime.utcnow() - timedelta(days=2)

        model2 = await ml_model_service.create_model_version(
            model_type="CATEGORIZATION",
            version="2.0.0",
            model_path="/models/v2.pkl",
        )
        model2.trained_at = datetime.utcnow()

        await db_session.commit()

        models = await ml_model_service.list_model_versions()
        assert len(models) == 2
        assert models[0].version == "2.0.0"  # Newest first
        assert models[1].version == "1.0.0"


class TestUpdateModelMetrics:
    """Tests for updating model metrics."""

    async def test_update_metrics_success(
        self,
        ml_model_service: MLModelService,
        db_session: AsyncSession,
    ):
        """Test updating model metrics."""
        model = await ml_model_service.create_model_version(
            model_type="CATEGORIZATION",
            version="1.0.0",
            model_path="/models/v1.pkl",
            accuracy=0.80,
        )
        await db_session.commit()

        updated = await ml_model_service.update_model_metrics(
            model.id,
            accuracy=0.85,
            precision=0.83,
            recall=0.87,
        )
        await db_session.commit()

        assert updated is not None
        assert updated.accuracy == 0.85
        assert updated.precision == 0.83
        assert updated.recall == 0.87

    async def test_update_partial_metrics(
        self,
        ml_model_service: MLModelService,
        db_session: AsyncSession,
    ):
        """Test updating only some metrics."""
        model = await ml_model_service.create_model_version(
            model_type="CATEGORIZATION",
            version="1.0.0",
            model_path="/models/v1.pkl",
            accuracy=0.80,
            precision=0.78,
        )
        await db_session.commit()

        updated = await ml_model_service.update_model_metrics(
            model.id,
            accuracy=0.85,
        )
        await db_session.commit()

        assert updated.accuracy == 0.85
        assert updated.precision == 0.78  # Unchanged

    async def test_update_metrics_nonexistent_model(
        self,
        ml_model_service: MLModelService,
    ):
        """Test updating metrics for nonexistent model returns None."""
        result = await ml_model_service.update_model_metrics(
            uuid4(),
            accuracy=0.85,
        )
        assert result is None

    async def test_update_metrics_invalid_value(
        self,
        ml_model_service: MLModelService,
        db_session: AsyncSession,
    ):
        """Test updating with invalid metric value raises error."""
        model = await ml_model_service.create_model_version(
            model_type="CATEGORIZATION",
            version="1.0.0",
            model_path="/models/v1.pkl",
        )
        await db_session.commit()

        with pytest.raises(ValueError, match="accuracy must be between 0 and 1"):
            await ml_model_service.update_model_metrics(
                model.id,
                accuracy=1.5,
            )


class TestActivateModelVersion:
    """Tests for activating model versions."""

    async def test_activate_model_success(
        self,
        ml_model_service: MLModelService,
        db_session: AsyncSession,
    ):
        """Test activating a model version."""
        model = await ml_model_service.create_model_version(
            model_type="CATEGORIZATION",
            version="1.0.0",
            model_path="/models/v1.pkl",
            is_active=False,
        )
        await db_session.commit()

        activated = await ml_model_service.activate_model_version(model.id)
        await db_session.commit()

        assert activated is not None
        assert activated.is_active is True

    async def test_activate_deactivates_others(
        self,
        ml_model_service: MLModelService,
        db_session: AsyncSession,
    ):
        """Test that activating one model deactivates others of same type."""
        model1 = await ml_model_service.create_model_version(
            model_type="CATEGORIZATION",
            version="1.0.0",
            model_path="/models/v1.pkl",
            is_active=True,
        )
        model2 = await ml_model_service.create_model_version(
            model_type="CATEGORIZATION",
            version="2.0.0",
            model_path="/models/v2.pkl",
            is_active=False,
        )
        await db_session.commit()

        await ml_model_service.activate_model_version(model2.id)
        await db_session.commit()

        # Refresh from database
        await db_session.refresh(model1)
        await db_session.refresh(model2)

        assert model1.is_active is False
        assert model2.is_active is True

    async def test_activate_different_type_unaffected(
        self,
        ml_model_service: MLModelService,
        db_session: AsyncSession,
    ):
        """Test that activating model doesn't affect different type."""
        cat_model = await ml_model_service.create_model_version(
            model_type="CATEGORIZATION",
            version="1.0.0",
            model_path="/models/cat.pkl",
            is_active=True,
        )
        pred_model = await ml_model_service.create_model_version(
            model_type="PREDICTION",
            version="1.0.0",
            model_path="/models/pred.pkl",
            is_active=False,
        )
        await db_session.commit()

        await ml_model_service.activate_model_version(pred_model.id)
        await db_session.commit()

        await db_session.refresh(cat_model)
        assert cat_model.is_active is True  # Unchanged


class TestDeactivateModelVersion:
    """Tests for deactivating model versions."""

    async def test_deactivate_model_success(
        self,
        ml_model_service: MLModelService,
        db_session: AsyncSession,
    ):
        """Test deactivating a model version."""
        model = await ml_model_service.create_model_version(
            model_type="CATEGORIZATION",
            version="1.0.0",
            model_path="/models/v1.pkl",
            is_active=True,
        )
        await db_session.commit()

        deactivated = await ml_model_service.deactivate_model_version(model.id)
        await db_session.commit()

        assert deactivated is not None
        assert deactivated.is_active is False


class TestRollbackToVersion:
    """Tests for rolling back to previous versions."""

    async def test_rollback_to_previous_version(
        self,
        ml_model_service: MLModelService,
        db_session: AsyncSession,
    ):
        """Test rolling back to a previous model version."""
        old_model = await ml_model_service.create_model_version(
            model_type="CATEGORIZATION",
            version="1.0.0",
            model_path="/models/v1.pkl",
            is_active=False,
            accuracy=0.85,
        )
        new_model = await ml_model_service.create_model_version(
            model_type="CATEGORIZATION",
            version="2.0.0",
            model_path="/models/v2.pkl",
            is_active=True,
            accuracy=0.75,  # Worse performance
        )
        await db_session.commit()

        # Rollback to old version
        rolled_back = await ml_model_service.rollback_to_version(old_model.id)
        await db_session.commit()

        await db_session.refresh(new_model)

        assert rolled_back.is_active is True
        assert new_model.is_active is False


class TestGetModelHistory:
    """Tests for retrieving model history."""

    async def test_get_model_history(
        self,
        ml_model_service: MLModelService,
        db_session: AsyncSession,
    ):
        """Test retrieving model version history."""
        for i in range(5):
            model = await ml_model_service.create_model_version(
                model_type="CATEGORIZATION",
                version=f"{i}.0.0",
                model_path=f"/models/v{i}.pkl",
            )
            model.trained_at = datetime.utcnow() - timedelta(days=5 - i)
        await db_session.commit()

        history = await ml_model_service.get_model_history(
            "CATEGORIZATION",
            limit=3,
        )

        assert len(history) == 3
        # Should be ordered newest first
        assert history[0].version == "4.0.0"
        assert history[1].version == "3.0.0"
        assert history[2].version == "2.0.0"

    async def test_get_user_model_history(
        self,
        ml_model_service: MLModelService,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test retrieving user-specific model history."""
        # Create global model
        await ml_model_service.create_model_version(
            model_type="CATEGORIZATION",
            version="1.0.0",
            model_path="/models/global.pkl",
        )

        # Create user models
        for i in range(3):
            await ml_model_service.create_model_version(
                model_type="CATEGORIZATION",
                version=f"{i}.0.0",
                model_path=f"/models/user_v{i}.pkl",
                user_id=test_user.id,
            )
        await db_session.commit()

        history = await ml_model_service.get_model_history(
            "CATEGORIZATION",
            user_id=test_user.id,
        )

        assert len(history) == 3
        assert all(m.user_id == test_user.id for m in history)


class TestCheckModelPerformance:
    """Tests for checking model performance."""

    async def test_check_performance_meets_threshold(
        self,
        ml_model_service: MLModelService,
        db_session: AsyncSession,
    ):
        """Test checking performance when model meets threshold."""
        model = await ml_model_service.create_model_version(
            model_type="CATEGORIZATION",
            version="1.0.0",
            model_path="/models/v1.pkl",
            accuracy=0.85,
        )
        await db_session.commit()

        result = await ml_model_service.check_model_performance(
            model.id,
            accuracy_threshold=0.80,
        )

        assert result["model_id"] == model.id
        assert result["accuracy"] == 0.85
        assert result["threshold"] == 0.80
        assert result["meets_threshold"] is True
        assert result["alert_required"] is False
        assert "acceptable" in result["message"].lower()

    async def test_check_performance_below_threshold(
        self,
        ml_model_service: MLModelService,
        db_session: AsyncSession,
    ):
        """Test checking performance when model is below threshold."""
        model = await ml_model_service.create_model_version(
            model_type="CATEGORIZATION",
            version="1.0.0",
            model_path="/models/v1.pkl",
            accuracy=0.75,
        )
        await db_session.commit()

        result = await ml_model_service.check_model_performance(
            model.id,
            accuracy_threshold=0.80,
        )

        assert result["model_id"] == model.id
        assert result["accuracy"] == 0.75
        assert result["threshold"] == 0.80
        assert result["meets_threshold"] is False
        assert result["alert_required"] is True
        assert "below threshold" in result["message"].lower()
        assert "retraining" in result["message"].lower()

    async def test_check_performance_no_accuracy(
        self,
        ml_model_service: MLModelService,
        db_session: AsyncSession,
    ):
        """Test checking performance when model has no accuracy metrics."""
        model = await ml_model_service.create_model_version(
            model_type="CATEGORIZATION",
            version="1.0.0",
            model_path="/models/v1.pkl",
        )
        await db_session.commit()

        result = await ml_model_service.check_model_performance(model.id)

        assert result["model_id"] == model.id
        assert result["accuracy"] is None
        assert result["meets_threshold"] is False
        assert result["alert_required"] is True
        assert "not available" in result["message"].lower()

    async def test_check_performance_nonexistent_model(
        self,
        ml_model_service: MLModelService,
    ):
        """Test checking performance for nonexistent model raises error."""
        with pytest.raises(ValueError, match="not found"):
            await ml_model_service.check_model_performance(uuid4())

    async def test_check_performance_custom_threshold(
        self,
        ml_model_service: MLModelService,
        db_session: AsyncSession,
    ):
        """Test checking performance with custom threshold."""
        model = await ml_model_service.create_model_version(
            model_type="CATEGORIZATION",
            version="1.0.0",
            model_path="/models/v1.pkl",
            accuracy=0.85,
        )
        await db_session.commit()

        # Should meet 0.80 threshold
        result1 = await ml_model_service.check_model_performance(
            model.id,
            accuracy_threshold=0.80,
        )
        assert result1["meets_threshold"] is True

        # Should not meet 0.90 threshold
        result2 = await ml_model_service.check_model_performance(
            model.id,
            accuracy_threshold=0.90,
        )
        assert result2["meets_threshold"] is False


class TestGetPerformanceAlerts:
    """Tests for getting performance alerts."""

    async def test_get_alerts_no_active_models(
        self,
        ml_model_service: MLModelService,
        db_session: AsyncSession,
    ):
        """Test getting alerts when no active models exist."""
        await ml_model_service.create_model_version(
            model_type="CATEGORIZATION",
            version="1.0.0",
            model_path="/models/v1.pkl",
            accuracy=0.75,
            is_active=False,
        )
        await db_session.commit()

        alerts = await ml_model_service.get_performance_alerts()
        assert len(alerts) == 0

    async def test_get_alerts_model_below_threshold(
        self,
        ml_model_service: MLModelService,
        db_session: AsyncSession,
    ):
        """Test getting alerts for model below threshold."""
        model = await ml_model_service.create_model_version(
            model_type="CATEGORIZATION",
            version="1.0.0",
            model_path="/models/v1.pkl",
            accuracy=0.75,
            is_active=True,
        )
        await db_session.commit()

        alerts = await ml_model_service.get_performance_alerts(accuracy_threshold=0.80)

        assert len(alerts) == 1
        assert alerts[0]["model_id"] == model.id
        assert alerts[0]["accuracy"] == 0.75
        assert alerts[0]["threshold"] == 0.80
        assert "requires attention" in alerts[0]["message"]

    async def test_get_alerts_model_above_threshold(
        self,
        ml_model_service: MLModelService,
        db_session: AsyncSession,
    ):
        """Test no alerts for model above threshold."""
        await ml_model_service.create_model_version(
            model_type="CATEGORIZATION",
            version="1.0.0",
            model_path="/models/v1.pkl",
            accuracy=0.85,
            is_active=True,
        )
        await db_session.commit()

        alerts = await ml_model_service.get_performance_alerts(accuracy_threshold=0.80)

        assert len(alerts) == 0

    async def test_get_alerts_model_no_accuracy(
        self,
        ml_model_service: MLModelService,
        db_session: AsyncSession,
    ):
        """Test alerts for model with no accuracy metrics."""
        model = await ml_model_service.create_model_version(
            model_type="CATEGORIZATION",
            version="1.0.0",
            model_path="/models/v1.pkl",
            is_active=True,
        )
        await db_session.commit()

        alerts = await ml_model_service.get_performance_alerts()

        assert len(alerts) == 1
        assert alerts[0]["model_id"] == model.id
        assert alerts[0]["accuracy"] is None
        assert "no accuracy metrics" in alerts[0]["message"]

    async def test_get_alerts_multiple_models(
        self,
        ml_model_service: MLModelService,
        db_session: AsyncSession,
    ):
        """Test alerts for multiple models with mixed performance."""
        # Good model
        await ml_model_service.create_model_version(
            model_type="CATEGORIZATION",
            version="1.0.0",
            model_path="/models/cat_v1.pkl",
            accuracy=0.85,
            is_active=True,
        )

        # Bad model
        bad_model = await ml_model_service.create_model_version(
            model_type="PREDICTION",
            version="1.0.0",
            model_path="/models/pred_v1.pkl",
            accuracy=0.70,
            is_active=True,
        )

        # Model without metrics
        no_metrics = await ml_model_service.create_model_version(
            model_type="CATEGORIZATION",
            version="2.0.0",
            model_path="/models/cat_v2.pkl",
            is_active=True,
        )

        await db_session.commit()

        alerts = await ml_model_service.get_performance_alerts(accuracy_threshold=0.80)

        assert len(alerts) == 2
        alert_ids = {alert["model_id"] for alert in alerts}
        assert bad_model.id in alert_ids
        assert no_metrics.id in alert_ids

    async def test_get_alerts_filter_by_type(
        self,
        ml_model_service: MLModelService,
        db_session: AsyncSession,
    ):
        """Test filtering alerts by model type."""
        cat_model = await ml_model_service.create_model_version(
            model_type="CATEGORIZATION",
            version="1.0.0",
            model_path="/models/cat.pkl",
            accuracy=0.75,
            is_active=True,
        )

        await ml_model_service.create_model_version(
            model_type="PREDICTION",
            version="1.0.0",
            model_path="/models/pred.pkl",
            accuracy=0.70,
            is_active=True,
        )

        await db_session.commit()

        alerts = await ml_model_service.get_performance_alerts(model_type="CATEGORIZATION")

        assert len(alerts) == 1
        assert alerts[0]["model_id"] == cat_model.id
        assert alerts[0]["model_type"] == "CATEGORIZATION"

    async def test_get_alerts_custom_threshold(
        self,
        ml_model_service: MLModelService,
        db_session: AsyncSession,
    ):
        """Test alerts with custom threshold."""
        model = await ml_model_service.create_model_version(
            model_type="CATEGORIZATION",
            version="1.0.0",
            model_path="/models/v1.pkl",
            accuracy=0.85,
            is_active=True,
        )
        await db_session.commit()

        # No alerts with 0.80 threshold
        alerts1 = await ml_model_service.get_performance_alerts(accuracy_threshold=0.80)
        assert len(alerts1) == 0

        # Alert with 0.90 threshold
        alerts2 = await ml_model_service.get_performance_alerts(accuracy_threshold=0.90)
        assert len(alerts2) == 1
        assert alerts2[0]["model_id"] == model.id
