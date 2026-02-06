"""Budget model for storing user budget information."""

from __future__ import annotations

import uuid
from datetime import datetime, date
from typing import TYPE_CHECKING, Any

from sqlalchemy import String, DateTime, Date, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class Budget(Base):
    """Budget model for storing budget allocations by category."""

    __tablename__ = "budgets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    period_end: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    allocations: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, comment="JSON object mapping category names to budget amounts"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="budgets")

    # Table constraints
    __table_args__ = (
        # Composite indexes for common queries
        Index("idx_budgets_user_period", "user_id", "period_start", "period_end"),
    )

    def __repr__(self) -> str:
        """String representation of Budget."""
        return (
            f"<Budget(id={self.id}, user_id={self.user_id}, "
            f"name={self.name}, period={self.period_start} to {self.period_end})>"
        )
