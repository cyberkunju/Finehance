"""ML Model version schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class MLModelVersionCreate(BaseModel):
    """Schema for creating a new ML model version."""

    model_type: str = Field(..., max_length=50)
    version: str = Field(..., max_length=20)
    model_path: str = Field(..., max_length=500)
    accuracy: Optional[float] = Field(None, ge=0.0, le=1.0)
    precision: Optional[float] = Field(None, ge=0.0, le=1.0)
    recall: Optional[float] = Field(None, ge=0.0, le=1.0)


class MLModelVersionResponse(BaseModel):
    """Schema for ML model version response."""

    id: UUID
    user_id: Optional[UUID] = None
    model_type: str
    version: str
    model_path: str
    accuracy: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    trained_at: datetime
    is_active: bool

    model_config = {"from_attributes": True}
