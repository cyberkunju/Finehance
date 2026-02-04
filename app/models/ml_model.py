"""ML model metadata for tracking machine learning models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    String, DateTime, Float, Boolean, ForeignKey, Index, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class MLModel(Base):
    """ML model metadata for tracking categorization and prediction models."""

    __tablename__ = "ml_models"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    model_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Type of model: CATEGORIZATION or PREDICTION"
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        comment="NULL for global models, user_id for user-specific models"
    )
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    accuracy: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    precision: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    recall: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    trained_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    model_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Path to model file in storage (S3 or file system)"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True
    )

    # Relationships
    user: Mapped[Optional["User"]] = relationship("User", back_populates="ml_models")

    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "model_type IN ('CATEGORIZATION', 'PREDICTION')",
            name="check_model_type"
        ),
        CheckConstraint(
            "accuracy IS NULL OR (accuracy >= 0 AND accuracy <= 1)",
            name="check_accuracy_range"
        ),
        CheckConstraint(
            "precision IS NULL OR (precision >= 0 AND precision <= 1)",
            name="check_precision_range"
        ),
        CheckConstraint(
            "recall IS NULL OR (recall >= 0 AND recall <= 1)",
            name="check_recall_range"
        ),
        # Composite indexes for common queries
        Index("idx_ml_models_type_active", "model_type", "is_active"),
        Index("idx_ml_models_user_type", "user_id", "model_type"),
        Index("idx_ml_models_user_type_active", "user_id", "model_type", "is_active"),
    )

    def __repr__(self) -> str:
        """String representation of MLModel."""
        return (
            f"<MLModel(id={self.id}, type={self.model_type}, "
            f"user_id={self.user_id}, version={self.version}, "
            f"accuracy={self.accuracy}, is_active={self.is_active})>"
        )
