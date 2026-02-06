"""Transaction model for storing financial transactions."""

from __future__ import annotations

import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    String,
    DateTime,
    Date,
    Numeric,
    Float,
    ForeignKey,
    Index,
    CheckConstraint,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.connection import Connection


class Transaction(Base):
    """Transaction model for storing income and expense records."""

    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(10), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float)
    connection_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("connections.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="transactions")
    connection: Mapped[Optional["Connection"]] = relationship(
        "Connection", back_populates="transactions"
    )

    # Table constraints
    __table_args__ = (
        CheckConstraint("type IN ('INCOME', 'EXPENSE')", name="check_transaction_type"),
        CheckConstraint(
            "source IN ('MANUAL', 'API', 'FILE_IMPORT')", name="check_transaction_source"
        ),
        CheckConstraint("amount >= 0", name="check_amount_positive"),
        CheckConstraint(
            "confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)",
            name="check_confidence_score_range",
        ),
        # Composite indexes for common queries
        Index("idx_transactions_user_date", "user_id", "date"),
        Index("idx_transactions_user_category", "user_id", "category"),
        Index("idx_transactions_user_type", "user_id", "type"),
        Index("idx_transactions_deleted", "deleted_at"),
    )

    def __repr__(self) -> str:
        """String representation of Transaction."""
        return (
            f"<Transaction(id={self.id}, user_id={self.user_id}, "
            f"amount={self.amount}, type={self.type})>"
        )
