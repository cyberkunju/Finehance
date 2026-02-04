"""Goal schemas for request/response validation."""

from datetime import date as date_type, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class GoalCreate(BaseModel):
    """Schema for creating a new goal."""

    name: str = Field(..., min_length=1, max_length=100, description="Goal name")
    target_amount: Decimal = Field(..., gt=0, description="Target amount to achieve")
    deadline: Optional[date_type] = Field(None, description="Optional deadline date")
    category: Optional[str] = Field(
        None, max_length=50, description="Optional category to link with transactions"
    )
    initial_amount: Decimal = Field(
        default=Decimal(0), ge=0, description="Initial amount (default: 0)"
    )

    @field_validator("target_amount", "initial_amount")
    @classmethod
    def validate_amounts(cls, v: Decimal) -> Decimal:
        """Validate amounts are properly formatted."""
        return round(v, 2)


class GoalUpdate(BaseModel):
    """Schema for updating a goal."""

    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Goal name")
    target_amount: Optional[Decimal] = Field(None, gt=0, description="Target amount")
    deadline: Optional[date_type] = Field(None, description="Deadline date")
    category: Optional[str] = Field(None, max_length=50, description="Category")
    status: Optional[str] = Field(None, description="Status (ACTIVE, ACHIEVED, ARCHIVED)")

    @field_validator("target_amount")
    @classmethod
    def validate_target_amount(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Validate target amount if provided."""
        if v is not None:
            return round(v, 2)
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        """Validate status if provided."""
        if v is not None and v not in ["ACTIVE", "ACHIEVED", "ARCHIVED"]:
            raise ValueError("Status must be ACTIVE, ACHIEVED, or ARCHIVED")
        return v


class GoalProgressUpdate(BaseModel):
    """Schema for updating goal progress."""

    amount: Decimal = Field(..., gt=0, description="Amount to add to progress")

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        """Validate amount is properly formatted."""
        return round(v, 2)


class GoalResponse(BaseModel):
    """Schema for goal response."""

    id: UUID
    user_id: UUID
    name: str
    target_amount: Decimal
    current_amount: Decimal
    deadline: Optional[date_type]
    category: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class GoalProgressResponse(BaseModel):
    """Schema for goal progress response."""

    goal_id: UUID
    name: str
    target_amount: Decimal
    current_amount: Decimal
    progress_percent: float
    remaining_amount: Decimal
    days_remaining: Optional[int]
    estimated_completion_date: Optional[date_type]
    is_at_risk: bool
    risk_reason: Optional[str]


class GoalRiskAlertResponse(BaseModel):
    """Schema for goal risk alert response."""

    goal_id: UUID
    name: str
    severity: str
    message: str
    recommended_action: str
