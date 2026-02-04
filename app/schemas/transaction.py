"""Transaction schemas for request/response validation."""

from datetime import date as date_type, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class TransactionType(str, Enum):
    """Transaction type enumeration."""
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"


class TransactionSource(str, Enum):
    """Transaction source enumeration."""
    MANUAL = "MANUAL"
    API = "API"
    FILE_IMPORT = "FILE_IMPORT"


class TransactionCreate(BaseModel):
    """Schema for creating a new transaction."""
    amount: Decimal = Field(..., gt=0, description="Transaction amount")
    date: date_type = Field(..., description="Transaction date")
    description: str = Field(..., min_length=1, max_length=500, description="Transaction description")
    type: TransactionType = Field(..., description="Transaction type (INCOME or EXPENSE)")
    source: TransactionSource = Field(default=TransactionSource.MANUAL, description="Transaction source")
    category: Optional[str] = Field(None, max_length=50, description="Transaction category (auto-assigned if not provided)")
    connection_id: Optional[UUID] = Field(None, description="Connection ID if from Financial API")

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        """Validate amount is positive and has max 2 decimal places."""
        if v <= 0:
            raise ValueError("Amount must be positive")
        # Round to 2 decimal places
        return round(v, 2)


class TransactionUpdate(BaseModel):
    """Schema for updating an existing transaction."""
    amount: Optional[Decimal] = Field(None, gt=0, description="Transaction amount")
    date: Optional[date_type] = Field(None, description="Transaction date")
    description: Optional[str] = Field(None, min_length=1, max_length=500, description="Transaction description")
    type: Optional[TransactionType] = Field(None, description="Transaction type")
    category: Optional[str] = Field(None, max_length=50, description="Transaction category")

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Validate amount if provided."""
        if v is not None:
            if v <= 0:
                raise ValueError("Amount must be positive")
            return round(v, 2)
        return v


class TransactionResponse(BaseModel):
    """Schema for transaction response."""
    id: UUID
    user_id: UUID
    amount: Decimal
    date: date_type
    description: str
    category: str
    type: TransactionType
    source: TransactionSource
    confidence_score: Optional[float] = None
    connection_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TransactionFilters(BaseModel):
    """Schema for filtering transactions."""
    start_date: Optional[date_type] = Field(None, description="Filter transactions from this date")
    end_date: Optional[date_type] = Field(None, description="Filter transactions until this date")
    category: Optional[str] = Field(None, description="Filter by category")
    type: Optional[TransactionType] = Field(None, description="Filter by type")
    min_amount: Optional[Decimal] = Field(None, ge=0, description="Minimum amount")
    max_amount: Optional[Decimal] = Field(None, ge=0, description="Maximum amount")
    search: Optional[str] = Field(None, max_length=200, description="Search in description")

    @field_validator("end_date")
    @classmethod
    def validate_date_range(cls, v: Optional[date_type], info) -> Optional[date_type]:
        """Validate end_date is after start_date."""
        if v is not None and "start_date" in info.data and info.data["start_date"] is not None:
            if v < info.data["start_date"]:
                raise ValueError("end_date must be after start_date")
        return v


class Pagination(BaseModel):
    """Schema for pagination parameters."""
    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(default=50, ge=1, le=100, description="Number of items per page")

    @property
    def offset(self) -> int:
        """Calculate offset for database query."""
        return (self.page - 1) * self.page_size


class PaginatedTransactionResponse(BaseModel):
    """Schema for paginated transaction list response."""
    items: list[TransactionResponse]
    total: int
    page: int
    page_size: int
    total_pages: int

    @property
    def has_next(self) -> bool:
        """Check if there are more pages."""
        return self.page < self.total_pages

    @property
    def has_prev(self) -> bool:
        """Check if there are previous pages."""
        return self.page > 1
