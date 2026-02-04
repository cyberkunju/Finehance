"""Connection model for financial API integrations."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    String, DateTime, Text, ForeignKey, Index, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.transaction import Transaction


def _get_encryption_service():
    """Lazy import to avoid circular dependencies."""
    from app.services.encryption_service import encryption_service
    return encryption_service


class Connection(Base):
    """Connection model for storing financial API connection information."""

    __tablename__ = "connections"

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
    institution_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Financial institution identifier from API provider"
    )
    institution_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Human-readable institution name"
    )
    _access_token_encrypted: Mapped[str] = mapped_column(
        "access_token",
        Text,
        nullable=False,
        comment="Encrypted access token for API authentication"
    )
    last_sync: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="Timestamp of last successful transaction sync"
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

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="connections")
    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction",
        back_populates="connection"
    )

    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE', 'EXPIRED', 'ERROR')",
            name="check_connection_status"
        ),
        # Composite indexes for common queries
        Index("idx_connections_user_status", "user_id", "status"),
        Index("idx_connections_user_institution", "user_id", "institution_id"),
    )

    @property
    def access_token(self) -> str:
        """Get decrypted access token.
        
        Returns:
            Decrypted access token string
        """
        encryption = _get_encryption_service()
        return encryption.decrypt(self._access_token_encrypted)

    @access_token.setter
    def access_token(self, value: str) -> None:
        """Set access token (will be encrypted before storage).
        
        Args:
            value: Plaintext access token to encrypt and store
        """
        encryption = _get_encryption_service()
        self._access_token_encrypted = encryption.encrypt(value)

    def __repr__(self) -> str:
        """String representation of Connection."""
        return (
            f"<Connection(id={self.id}, user_id={self.user_id}, "
            f"institution={self.institution_name}, status={self.status})>"
        )
