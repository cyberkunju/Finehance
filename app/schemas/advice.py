"""Advice schemas for request/response validation."""

from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class AdviceResponse(BaseModel):
    """Schema for financial advice response."""

    title: str
    message: str
    explanation: str
    priority: str = Field(..., description="CRITICAL, HIGH, MEDIUM, or LOW")
    category: Optional[str] = None
    action_items: Optional[List[str]] = None
    related_id: Optional[UUID] = Field(None, description="Related budget/goal ID")
