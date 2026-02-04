"""Pydantic schemas for authentication API endpoints."""

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserRegisterRequest(BaseModel):
    """Request schema for user registration."""
    
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=12, description="User password (min 12 characters)")
    first_name: Optional[str] = Field(None, max_length=100, description="User's first name")
    last_name: Optional[str] = Field(None, max_length=100, description="User's last name")


class UserLoginRequest(BaseModel):
    """Request schema for user login."""
    
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")


class TokenRefreshRequest(BaseModel):
    """Request schema for token refresh."""
    
    refresh_token: str = Field(..., description="Refresh token")


class TokenResponse(BaseModel):
    """Response schema for token operations."""
    
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(default=1800, description="Access token expiration in seconds (30 minutes)")


class UserResponse(BaseModel):
    """Response schema for user information."""
    
    model_config = {"from_attributes": True}
    
    id: UUID
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    created_at: str


class AuthResponse(BaseModel):
    """Response schema for authentication operations."""
    
    user: UserResponse
    tokens: TokenResponse


class MessageResponse(BaseModel):
    """Generic message response."""
    
    message: str
