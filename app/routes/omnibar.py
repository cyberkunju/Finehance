"""
OmniBar API Routes — Universal Natural Language Command Interface.

Provides:
- POST /api/omnibar/process  — Process a natural language command
- GET  /api/omnibar/suggest  — Get autocomplete suggestions
- GET  /api/omnibar/history  — Get conversation history
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.database import get_db
from app.dependencies import get_current_user_id
from app.logging_config import get_logger
from app.services.omnibar_service import OmniBarService, OmniResponse

logger = get_logger(__name__)
router = APIRouter()

limiter = Limiter(key_func=get_remote_address)


# ---- Request/Response Models ----


class OmniBarRequest(BaseModel):
    """Request for processing a natural language command."""

    message: str = Field(..., min_length=1, max_length=2000, description="Natural language input")
    history: Optional[List[dict]] = Field(
        None, description="Previous conversation messages for context"
    )


class OmniBarResponse(BaseModel):
    """Response from the OmniBar processing."""

    success: bool
    message: str
    intent: str
    data: Optional[dict] = None
    suggestions: Optional[List[str]] = None
    confidence: float = 1.0


class SuggestionResponse(BaseModel):
    """Autocomplete suggestions."""

    suggestions: List[str]


# ---- Endpoints ----


@router.post("/process", response_model=OmniBarResponse)
@limiter.limit("30/minute")
async def process_command(
    request: Request,
    body: OmniBarRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> OmniBarResponse:
    """
    Process a natural language command through the OmniBar.

    The OmniBar understands commands like:
    - "Spent 250rs on lunch yesterday" → Creates a transaction
    - "How much did I spend on food last month?" → Returns spending data
    - "Save 50000 for a laptop by December" → Creates a goal
    - "Set food budget to 5000 this month" → Creates a budget
    - "Am I over budget?" → Returns budget status
    - "Show my goals progress" → Returns goal progress
    - General financial questions → AI-powered response

    Rate limited to 30 requests/minute per user.
    """
    try:
        service = OmniBarService(db, user_id)
        result: OmniResponse = await service.process(
            text=body.message,
            history=body.history,
        )

        return OmniBarResponse(
            success=result.success,
            message=result.message,
            intent=result.intent,
            data=result.data,
            suggestions=result.suggestions,
            confidence=result.confidence,
        )

    except Exception as e:
        logger.error(f"OmniBar processing error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to process your command. Please try again.",
        )


@router.get("/suggest", response_model=SuggestionResponse)
@limiter.limit("60/minute")
async def get_suggestions(
    request: Request,
    q: str = Query("", max_length=200, description="Partial input text"),
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> SuggestionResponse:
    """
    Get autocomplete suggestions for partial OmniBar input.

    Rate limited to 60 requests/minute per user.
    """
    try:
        service = OmniBarService(db, user_id)
        suggestions = await service.get_suggestions(q)

        return SuggestionResponse(suggestions=suggestions)

    except Exception as e:
        logger.error(f"OmniBar suggestion error: {e}", exc_info=True)
        return SuggestionResponse(suggestions=[])
