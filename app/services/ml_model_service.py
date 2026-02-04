"""Service for managing ML model metadata and versioning."""

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ml_model import MLModel


class MLModelService:
    """Service for tracking and managing ML model versions."""

    def __init__(self, db_session: AsyncSession):
        """Initialize ML model service.
        
        Args:
            db_session: Database session for queries
        """
        self.db = db_session

    async def create_model_version(
        self,
        model_type: str,
        version: str,
        model_path: str,
        accuracy: Optional[float] = None,
        precision: Optional[float] = None,
        recall: Optional[float] = None,
        user_id: Optional[UUID] = None,
        is_active: bool = False,
    ) -> MLModel:
        """Create a new model version record.
        
        Args:
            model_type: Type of model (CATEGORIZATION or PREDICTION)
            version: Version string (e.g., "1.0.0", "2024-01-30")
            model_path: Path to model file in storage
            accuracy: Model accuracy metric (0-1)
            precision: Model precision metric (0-1)
            recall: Model recall metric (0-1)
            user_id: User ID for user-specific models, None for global models
            is_active: Whether this version should be active
            
        Returns:
            Created MLModel instance
            
        Raises:
            ValueError: If model_type is invalid or metrics are out of range
        """
        # Validate model type
        if model_type not in ("CATEGORIZATION", "PREDICTION"):
            raise ValueError(f"Invalid model_type: {model_type}")
        
        # Validate metrics
        for metric_name, metric_value in [
            ("accuracy", accuracy),
            ("precision", precision),
            ("recall", recall),
        ]:
            if metric_value is not None and not (0 <= metric_value <= 1):
                raise ValueError(
                    f"{metric_name} must be between 0 and 1, got {metric_value}"
                )
        
        model = MLModel(
            model_type=model_type,
            user_id=user_id,
            version=version,
            accuracy=accuracy,
            precision=precision,
            recall=recall,
            trained_at=datetime.utcnow(),
            model_path=model_path,
            is_active=is_active,
        )
        
        self.db.add(model)
        await self.db.flush()
        
        return model

    async def get_model_version(
        self,
        model_id: UUID,
    ) -> Optional[MLModel]:
        """Get a specific model version by ID.
        
        Args:
            model_id: Model ID
            
        Returns:
            MLModel instance or None if not found
        """
        result = await self.db.execute(
            select(MLModel).filter_by(id=model_id)
        )
        return result.scalar_one_or_none()

    async def get_active_model(
        self,
        model_type: str,
        user_id: Optional[UUID] = None,
    ) -> Optional[MLModel]:
        """Get the currently active model for a type and user.
        
        Args:
            model_type: Type of model (CATEGORIZATION or PREDICTION)
            user_id: User ID for user-specific models, None for global models
            
        Returns:
            Active MLModel instance or None if not found
        """
        result = await self.db.execute(
            select(MLModel).filter(
                and_(
                    MLModel.model_type == model_type,
                    MLModel.user_id == user_id,
                    MLModel.is_active == True,
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_model_versions(
        self,
        model_type: Optional[str] = None,
        user_id: Optional[UUID] = None,
        is_active: Optional[bool] = None,
    ) -> List[MLModel]:
        """List model versions with optional filters.
        
        Args:
            model_type: Filter by model type
            user_id: Filter by user ID
            is_active: Filter by active status
            
        Returns:
            List of MLModel instances ordered by trained_at descending
        """
        query = select(MLModel)
        
        filters = []
        if model_type is not None:
            filters.append(MLModel.model_type == model_type)
        if user_id is not None:
            filters.append(MLModel.user_id == user_id)
        if is_active is not None:
            filters.append(MLModel.is_active == is_active)
        
        if filters:
            query = query.filter(and_(*filters))
        
        query = query.order_by(desc(MLModel.trained_at))
        
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_model_metrics(
        self,
        model_id: UUID,
        accuracy: Optional[float] = None,
        precision: Optional[float] = None,
        recall: Optional[float] = None,
    ) -> Optional[MLModel]:
        """Update metrics for a model version.
        
        Args:
            model_id: Model ID
            accuracy: New accuracy value
            precision: New precision value
            recall: New recall value
            
        Returns:
            Updated MLModel instance or None if not found
            
        Raises:
            ValueError: If metrics are out of range
        """
        model = await self.get_model_version(model_id)
        if not model:
            return None
        
        # Validate metrics
        for metric_name, metric_value in [
            ("accuracy", accuracy),
            ("precision", precision),
            ("recall", recall),
        ]:
            if metric_value is not None and not (0 <= metric_value <= 1):
                raise ValueError(
                    f"{metric_name} must be between 0 and 1, got {metric_value}"
                )
        
        if accuracy is not None:
            model.accuracy = accuracy
        if precision is not None:
            model.precision = precision
        if recall is not None:
            model.recall = recall
        
        await self.db.flush()
        return model

    async def activate_model_version(
        self,
        model_id: UUID,
    ) -> Optional[MLModel]:
        """Activate a model version and deactivate others of same type/user.
        
        This ensures only one model of each type is active per user.
        
        Args:
            model_id: Model ID to activate
            
        Returns:
            Activated MLModel instance or None if not found
        """
        model = await self.get_model_version(model_id)
        if not model:
            return None
        
        # Deactivate all other models of same type and user
        result = await self.db.execute(
            select(MLModel).filter(
                and_(
                    MLModel.model_type == model.model_type,
                    MLModel.user_id == model.user_id,
                    MLModel.is_active == True,
                    MLModel.id != model_id,
                )
            )
        )
        other_models = result.scalars().all()
        for other_model in other_models:
            other_model.is_active = False
        
        # Activate the target model
        model.is_active = True
        
        await self.db.flush()
        return model

    async def deactivate_model_version(
        self,
        model_id: UUID,
    ) -> Optional[MLModel]:
        """Deactivate a model version.
        
        Args:
            model_id: Model ID to deactivate
            
        Returns:
            Deactivated MLModel instance or None if not found
        """
        model = await self.get_model_version(model_id)
        if not model:
            return None
        
        model.is_active = False
        await self.db.flush()
        return model

    async def rollback_to_version(
        self,
        model_id: UUID,
    ) -> Optional[MLModel]:
        """Rollback to a previous model version by activating it.
        
        This is an alias for activate_model_version with clearer intent.
        
        Args:
            model_id: Model ID to rollback to
            
        Returns:
            Activated MLModel instance or None if not found
        """
        return await self.activate_model_version(model_id)

    async def get_model_history(
        self,
        model_type: str,
        user_id: Optional[UUID] = None,
        limit: int = 10,
    ) -> List[MLModel]:
        """Get version history for a model type.
        
        Args:
            model_type: Type of model (CATEGORIZATION or PREDICTION)
            user_id: User ID for user-specific models, None for global models
            limit: Maximum number of versions to return
            
        Returns:
            List of MLModel instances ordered by trained_at descending
        """
        result = await self.db.execute(
            select(MLModel)
            .filter(
                and_(
                    MLModel.model_type == model_type,
                    MLModel.user_id == user_id,
                )
            )
            .order_by(desc(MLModel.trained_at))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def check_model_performance(
        self,
        model_id: UUID,
        accuracy_threshold: float = 0.80,
    ) -> dict:
        """Check if model performance meets threshold requirements.
        
        Args:
            model_id: Model ID to check
            accuracy_threshold: Minimum acceptable accuracy (default: 0.80)
            
        Returns:
            Dictionary with performance status:
            {
                "model_id": UUID,
                "accuracy": float,
                "threshold": float,
                "meets_threshold": bool,
                "alert_required": bool,
                "message": str
            }
            
        Raises:
            ValueError: If model not found
        """
        model = await self.get_model_version(model_id)
        if not model:
            raise ValueError(f"Model {model_id} not found")
        
        # Check if accuracy is available
        if model.accuracy is None:
            return {
                "model_id": model_id,
                "accuracy": None,
                "threshold": accuracy_threshold,
                "meets_threshold": False,
                "alert_required": True,
                "message": "Model accuracy not available - metrics need to be recorded"
            }
        
        meets_threshold = model.accuracy >= accuracy_threshold
        alert_required = not meets_threshold
        
        if meets_threshold:
            message = f"Model performance is acceptable (accuracy: {model.accuracy:.2%})"
        else:
            message = (
                f"Model performance below threshold "
                f"(accuracy: {model.accuracy:.2%} < {accuracy_threshold:.2%}) - "
                f"retraining recommended"
            )
        
        return {
            "model_id": model_id,
            "accuracy": model.accuracy,
            "threshold": accuracy_threshold,
            "meets_threshold": meets_threshold,
            "alert_required": alert_required,
            "message": message
        }

    async def get_performance_alerts(
        self,
        accuracy_threshold: float = 0.80,
        model_type: Optional[str] = None,
    ) -> List[dict]:
        """Get list of models that require performance alerts.
        
        Args:
            accuracy_threshold: Minimum acceptable accuracy (default: 0.80)
            model_type: Filter by model type (optional)
            
        Returns:
            List of alert dictionaries for models below threshold
        """
        # Get all active models
        query = select(MLModel).filter(MLModel.is_active == True)
        
        if model_type:
            query = query.filter(MLModel.model_type == model_type)
        
        result = await self.db.execute(query)
        active_models = result.scalars().all()
        
        alerts = []
        for model in active_models:
            # Check if model has accuracy and if it's below threshold
            if model.accuracy is None or model.accuracy < accuracy_threshold:
                alert = {
                    "model_id": model.id,
                    "model_type": model.model_type,
                    "version": model.version,
                    "accuracy": model.accuracy,
                    "threshold": accuracy_threshold,
                    "user_id": model.user_id,
                    "trained_at": model.trained_at,
                    "message": (
                        f"{model.model_type} model (v{model.version}) "
                        f"requires attention - "
                        f"accuracy: {model.accuracy:.2%} < {accuracy_threshold:.2%}"
                        if model.accuracy is not None
                        else f"{model.model_type} model (v{model.version}) "
                        f"has no accuracy metrics recorded"
                    )
                }
                alerts.append(alert)
        
        return alerts
