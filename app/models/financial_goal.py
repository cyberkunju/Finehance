"""Financial goal model for tracking user financial objectives."""

from __future__ import annotations

import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    String, DateTime, Date, Numeric, ForeignKey, Index, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class FinancialGoal(Base):
    """Financial goal model for tracking savings and financial objectives."""

    __tablename__ = "financial_goals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    target_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False
    )
    current_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=Decimal("0.00"),
        nullable=False
    )
    deadline: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Optional category to link goal with transactions"
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="ACTIVE",
        nullable=False,
        index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="financial_goals")

    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE', 'ACHIEVED', 'ARCHIVED')",
            name="check_goal_status"
        ),
        CheckConstraint(
            "target_amount > 0",
            name="check_target_amount_positive"
        ),
        CheckConstraint(
            "current_amount >= 0",
            name="check_current_amount_non_negative"
        ),
        # Composite indexes for common queries
        Index("idx_financial_goals_user_status", "user_id", "status"),
        Index("idx_financial_goals_user_deadline", "user_id", "deadline"),
    )

    def __repr__(self) -> str:
        """String representation of FinancialGoal."""
        return (
            f"<FinancialGoal(id={self.id}, user_id={self.user_id}, "
            f"name={self.name}, target={self.target_amount}, "
            f"current={self.current_amount}, status={self.status})>"
        )
