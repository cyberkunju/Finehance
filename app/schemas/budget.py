"""Budget schemas for request/response validation."""

from datetime import date as date_type, datetime
from decimal import Decimal
from typing import Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class BudgetCreate(BaseModel):
    """Schema for creating a new budget."""
    name: str = Field(..., min_length=1, max_length=100, description="Budget name")
    period_start: date_type = Field(..., description="Budget period start date")
    period_end: date_type = Field(..., description="Budget period end date")
    allocations: Dict[str, Decimal] = Field(..., description="Category allocations")

    @field_validator("period_end")
    @classmethod
    def validate_period(cls, v: date_type, info) -> date_type:
        """Validate period_end is after period_start."""
        if "period_start" in info.data and v < info.data["period_start"]:
            raise ValueError("period_end must be after period_start")
        return v

    @field_validator("allocations")
    @classmethod
    def validate_allocations(cls, v: Dict[str, Decimal]) -> Dict[str, Decimal]:
        """Validate allocations are positive."""
        for category, amount in v.items():
            if amount <= 0:
                raise ValueError(f"Allocation for {category} must be positive")
        return v


class BudgetUpdate(BaseModel):
    """Schema for updating a budget."""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Budget name")
    allocations: Optional[Dict[str, Decimal]] = Field(None, description="Category allocations")

    @field_validator("allocations")
    @classmethod
    def validate_allocations(cls, v: Optional[Dict[str, Decimal]]) -> Optional[Dict[str, Decimal]]:
        """Validate allocations if provided."""
        if v is not None:
            for category, amount in v.items():
                if amount <= 0:
                    raise ValueError(f"Allocation for {category} must be positive")
        return v


class BudgetResponse(BaseModel):
    """Schema for budget response."""
    id: UUID
    user_id: UUID
    name: str
    period_start: date_type
    period_end: date_type
    allocations: Dict[str, float]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BudgetProgressResponse(BaseModel):
    """Schema for budget progress response."""
    category: str
    allocated: Decimal
    spent: Decimal
    remaining: Decimal
    percent_used: float
    status: str


class BudgetAlertResponse(BaseModel):
    """Schema for budget alert response."""
    category: str
    allocated: Decimal
    spent: Decimal
    percent_over: float
    severity: str
    message: str


class BudgetSuggestionResponse(BaseModel):
    """Schema for budget optimization suggestion."""
    category: str
    current_allocation: Decimal
    suggested_allocation: Decimal
    change_amount: Decimal
    change_percent: float
    reason: str
    priority: str


class ApplyOptimizationRequest(BaseModel):
    """Schema for applying budget optimization."""
    suggestions: list[BudgetSuggestionResponse]
    user_approved: bool = Field(..., description="User approval required")
