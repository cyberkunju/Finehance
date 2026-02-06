"""Connection schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ConnectionCreate(BaseModel):
    """Schema for creating a new connection."""

    user_id: UUID
    institution_name: str = Field(..., max_length=100)
    institution_id: str = Field(..., max_length=100)
    status: str = Field(default="active", max_length=20)


class ConnectionResponse(BaseModel):
    """Schema for connection response."""

    id: UUID
    user_id: UUID
    institution_name: str
    institution_id: str
    status: str
    last_sync: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConnectionUpdate(BaseModel):
    """Schema for updating a connection."""

    status: Optional[str] = Field(None, max_length=20)
    institution_name: Optional[str] = Field(None, max_length=100)
