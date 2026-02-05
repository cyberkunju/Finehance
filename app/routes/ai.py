"""AI Brain API endpoints for intelligent financial assistance."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.database import get_db
from app.services.ai_brain_service import (
    AIBrainService,
    get_ai_brain,
)
from app.config import settings
from app.logging_config import get_logger
from app.middleware.input_guard import InputGuard
from app.middleware.output_guard import OutputGuard

logger = get_logger(__name__)
router = APIRouter()

# Rate limiter for AI endpoints (stricter limits due to GPU cost)
limiter = Limiter(key_func=get_remote_address)

# Input guard for prompt injection protection
input_guard = InputGuard(
    max_input_length=4000,
    risk_threshold=25.0,
    strict_mode=True,  # Block any HIGH/CRITICAL threats
    log_threats=True,
)

# Output guard for content filtering
output_guard = OutputGuard(
    mask_pii=True,
    filter_profanity=True,
    require_disclaimer=True,
    strict_mode=True,  # Block harmful financial advice
    auto_add_disclaimer=False,  # Route handlers add disclaimers if needed
    log_issues=True,
)


def validate_ai_input(text: str, field_name: str = "input") -> str:
    """
    Validate AI input for prompt injection attacks.

    Args:
        text: The input text to validate
        field_name: Name of the field for error messages

    Returns:
        Sanitized input text

    Raises:
        HTTPException: If input is rejected due to security concerns
    """
    result = input_guard.validate(text)

    if not result.is_safe:
        logger.warning(
            f"AI input rejected: {result.rejection_reason}",
            extra={
                "field": field_name,
                "threat_level": result.threat_level.value,
                "risk_score": result.risk_score,
            },
        )
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Input validation failed",
                "reason": "Your message contains patterns that cannot be processed",
                "code": "PROMPT_INJECTION_DETECTED",
            },
        )

    # Return sanitized input
    return result.sanitized_input or text


def validate_ai_output(
    response_text: str,
    context: Optional[dict] = None,
    fallback: str = "I cannot provide a response at this time. Please try rephrasing your question.",
) -> str:
    """
    Validate AI output for harmful content, PII, and hallucinations.

    Args:
        response_text: The AI response to validate
        context: Optional context about user-provided data
        fallback: Fallback message if response is blocked

    Returns:
        Filtered/safe response text
    """
    result = output_guard.validate(response_text, context)

    if not result.is_safe:
        logger.warning(
            f"AI output blocked: {result.max_severity.name} severity issues",
            extra={
                "issue_count": len(result.issues),
                "max_severity": result.max_severity.name,
                "pii_detected": result.pii_detected,
                "issue_types": [i.issue_type.name for i in result.issues[:5]],
            },
        )
        return fallback

    # Log if PII was masked
    if result.pii_detected:
        logger.info("PII masked in AI response", extra={"modified": result.content_modified})

    # Return filtered content (PII masked, profanity filtered)
    return result.filtered_content or response_text


def get_user_or_ip(request: Request) -> str:
    """Get user ID if authenticated, otherwise IP address.

    This allows per-user rate limiting for authenticated users,
    falling back to IP-based limiting for anonymous requests.
    """
    # Check if user is set on request state (from auth middleware)
    if hasattr(request.state, "user") and request.state.user:
        return f"user:{request.state.user.id}"

    # Check for user_id in request body (for endpoints with user context)
    # This is a fallback for routes that receive user_id in payload
    return get_remote_address(request)


# Request/Response Models
class ChatMessage(BaseModel):
    """A chat message."""

    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")


class ChatRequest(BaseModel):
    """Request for chat endpoint."""

    message: str = Field(..., description="User message", min_length=1, max_length=2000)
    user_id: Optional[UUID] = Field(None, description="User ID for personalization")
    history: Optional[List[ChatMessage]] = Field(None, description="Conversation history")
    context: Optional[dict] = Field(None, description="Financial context")


class ChatResponse(BaseModel):
    """Response from chat endpoint."""

    response: str
    mode: str
    confidence: float
    processing_time_ms: float
    from_cache: bool = False


class AnalysisRequest(BaseModel):
    """Request for financial analysis."""

    request: str = Field(..., description="Analysis request", min_length=1, max_length=2000)
    user_id: Optional[UUID] = Field(None, description="User ID")
    context: dict = Field(..., description="Financial context with spending, income, goals")


class TransactionParseRequest(BaseModel):
    """Request to parse a transaction description."""

    description: str = Field(
        ..., description="Transaction description", min_length=1, max_length=500
    )


class TransactionParseResponse(BaseModel):
    """Parsed transaction data."""

    merchant: Optional[str] = None
    category: Optional[str] = None
    merchant_type: Optional[str] = None
    location: Optional[str] = None
    is_recurring: bool = False
    confidence: float
    raw_response: str


class SmartAdviceRequest(BaseModel):
    """Request for smart financial advice."""

    user_id: UUID = Field(..., description="User ID")
    include_transactions: bool = Field(True, description="Include recent transaction context")
    include_goals: bool = Field(True, description="Include goals context")
    max_recommendations: int = Field(5, ge=1, le=10, description="Max recommendations")


class AIStatusResponse(BaseModel):
    """AI Brain status response."""

    enabled: bool
    mode: str
    available: bool
    model_loaded: bool = False
    fallback_active: bool = False
    resilience: Optional[dict] = None  # Phase 2: Resilience stats


# Endpoints
@router.get("/status", response_model=AIStatusResponse)
@limiter.limit("30/minute")  # Status check is lightweight
async def get_ai_status(
    request: Request,
    include_resilience: bool = Query(False, description="Include resilience stats"),
    ai_brain: AIBrainService = Depends(get_ai_brain),
) -> AIStatusResponse:
    """Get AI Brain service status.

    Rate limited to 30 requests per minute per IP.

    Set include_resilience=true to get circuit breaker and queue stats.
    """
    is_available = await ai_brain._check_availability()

    response = AIStatusResponse(
        enabled=settings.ai_brain_enabled,
        mode=settings.ai_brain_mode,
        available=is_available,
        fallback_active=not is_available and settings.ai_brain_enabled,
    )

    if include_resilience:
        response.resilience = ai_brain.get_resilience_stats()

    return response


@router.post("/chat", response_model=ChatResponse)
@limiter.limit(f"{settings.ai_rate_limit_per_minute}/minute", key_func=get_user_or_ip)
@limiter.limit(f"{settings.ai_rate_limit_per_hour}/hour", key_func=get_user_or_ip)
async def chat_with_ai(
    request: Request,
    chat_request: ChatRequest,
    ai_brain: AIBrainService = Depends(get_ai_brain),
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    """
    Chat with the Financial AI Brain.

    Rate limited to 5 requests/minute and 100 requests/hour per user/IP.

    The AI can help with:
    - Answering financial questions
    - Providing personalized advice
    - Explaining financial concepts
    - Analyzing spending patterns
    """
    if not settings.ai_brain_enabled:
        raise HTTPException(status_code=503, detail="AI Brain is disabled")

    # Validate input for prompt injection attacks
    safe_message = validate_ai_input(chat_request.message, "message")

    # Also validate history messages if provided
    if chat_request.history:
        for i, msg in enumerate(chat_request.history):
            validate_ai_input(msg.content, f"history[{i}].content")

    try:
        # Build context if user_id provided
        context = chat_request.context
        if chat_request.user_id and not context:
            context = await _build_user_context(db, chat_request.user_id)

        # Convert history to expected format
        history = None
        if chat_request.history:
            history = [{"role": m.role, "content": m.content} for m in chat_request.history]

        result = await ai_brain.chat(
            message=safe_message,
            context=context,
            history=history,
        )

        # Validate and filter AI output for harmful content, PII, etc.
        safe_response = validate_ai_output(
            result.response,
            context={"user_provided_data": str(context) if context else ""},
        )

        return ChatResponse(
            response=safe_response,
            mode=result.mode.value,
            confidence=result.confidence,
            processing_time_ms=result.processing_time_ms,
            from_cache=result.from_cache,
        )

    except Exception as e:
        logger.error("Chat failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


@router.post("/analyze", response_model=ChatResponse)
@limiter.limit(f"{settings.ai_rate_limit_per_minute}/minute", key_func=get_user_or_ip)
@limiter.limit(f"{settings.ai_rate_limit_per_hour}/hour", key_func=get_user_or_ip)
async def analyze_finances(
    request: Request,
    analysis_request: AnalysisRequest,
    ai_brain: AIBrainService = Depends(get_ai_brain),
) -> ChatResponse:
    """
    Request deep financial analysis from the AI Brain.

    Rate limited to 5 requests/minute and 100 requests/hour per user/IP.
    Provide spending data, income, and goals for comprehensive analysis.
    """
    if not settings.ai_brain_enabled:
        raise HTTPException(status_code=503, detail="AI Brain is disabled")

    # Validate input for prompt injection attacks
    safe_request = validate_ai_input(analysis_request.request, "request")

    try:
        result = await ai_brain.analyze(
            request=safe_request,
            context=analysis_request.context,
        )

        # Validate and filter AI output for harmful content, PII, etc.
        safe_response = validate_ai_output(
            result.response,
            context={
                "user_provided_data": str(analysis_request.context)
                if analysis_request.context
                else ""
            },
        )

        return ChatResponse(
            response=safe_response,
            mode=result.mode.value,
            confidence=result.confidence,
            processing_time_ms=result.processing_time_ms,
            from_cache=result.from_cache,
        )

    except Exception as e:
        logger.error("Analysis failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/parse-transaction", response_model=TransactionParseResponse)
@limiter.limit(f"{settings.ai_rate_limit_parse_per_minute}/minute", key_func=get_user_or_ip)
async def parse_transaction(
    request: Request,
    parse_request: TransactionParseRequest,
    ai_brain: AIBrainService = Depends(get_ai_brain),
) -> TransactionParseResponse:
    """
    Parse a transaction description to extract structured data.

    Rate limited to 30 requests/minute per user/IP (higher limit for batch imports).

    The AI will identify:
    - Merchant name
    - Category
    - Merchant type (online, retail, etc.)
    - Whether it's a recurring transaction
    """
    # Validate input for prompt injection attacks
    safe_description = validate_ai_input(parse_request.description, "description")

    try:
        result = await ai_brain.parse_transaction(safe_description)

        parsed = result.parsed_data or {}

        return TransactionParseResponse(
            merchant=parsed.get("merchant"),
            category=parsed.get("category"),
            merchant_type=parsed.get("merchant_type"),
            location=parsed.get("location"),
            is_recurring=parsed.get("is_recurring", False),
            confidence=result.confidence,
            raw_response=result.response,
        )

    except Exception as e:
        logger.error("Transaction parsing failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Parsing failed: {str(e)}")


@router.post("/smart-advice")
@limiter.limit(f"{settings.ai_rate_limit_per_minute}/minute", key_func=get_user_or_ip)
@limiter.limit(f"{settings.ai_rate_limit_per_hour}/hour", key_func=get_user_or_ip)
async def get_smart_advice(
    request: Request,
    advice_request: SmartAdviceRequest,
    ai_brain: AIBrainService = Depends(get_ai_brain),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get AI-powered personalized financial advice.

    Rate limited to 5 requests/minute and 100 requests/hour per user/IP.

    Combines user's transaction history, spending patterns, and goals
    to provide specific, actionable recommendations.
    """
    if not settings.ai_brain_enabled:
        raise HTTPException(status_code=503, detail="AI Brain is disabled")

    try:
        # Build comprehensive context
        context = await _build_user_context(db, advice_request.user_id)
        transactions = []
        goals = []

        if advice_request.include_transactions:
            transactions = await _get_recent_transactions(db, advice_request.user_id)

        if advice_request.include_goals:
            goals = await _get_user_goals(db, advice_request.user_id)

        advice = await ai_brain.get_smart_advice(
            user_context=context,
            recent_transactions=transactions,
            goals=goals,
        )

        # Validate and filter AI output for harmful content, PII, etc.
        # Smart advice is critical - must be filtered for harmful financial advice
        safe_advice = advice
        if isinstance(advice, str):
            safe_advice = validate_ai_output(
                advice,
                context={"user_provided_data": str(context) if context else ""},
            )
        elif isinstance(advice, list):
            # If advice is a list of strings, validate each
            safe_advice = [
                validate_ai_output(a, context={"user_provided_data": str(context)})
                if isinstance(a, str)
                else a
                for a in advice
            ]

        return {
            "advice": safe_advice,
            "generated_at": "now",
            "context_summary": {
                "transactions_analyzed": len(transactions),
                "goals_count": len(goals),
            },
        }

    except Exception as e:
        logger.error("Smart advice failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Smart advice failed: {str(e)}")


# Helper functions
async def _build_user_context(db: AsyncSession, user_id: UUID) -> dict:
    """Build financial context for a user."""
    from sqlalchemy import select, func, and_
    from datetime import datetime, timedelta
    from app.models.transaction import Transaction

    # Get spending by category for last 30 days
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)

    stmt = (
        select(Transaction.category, func.sum(Transaction.amount).label("total"))
        .where(
            and_(
                Transaction.user_id == user_id,
                Transaction.type == "EXPENSE",
                Transaction.date >= thirty_days_ago.date(),
                Transaction.deleted_at.is_(None),
            )
        )
        .group_by(Transaction.category)
    )

    result = await db.execute(stmt)
    spending = {row.category: float(row.total) for row in result.all()}

    # Get income
    income_stmt = select(func.sum(Transaction.amount)).where(
        and_(
            Transaction.user_id == user_id,
            Transaction.type == "INCOME",
            Transaction.date >= thirty_days_ago.date(),
            Transaction.deleted_at.is_(None),
        )
    )
    income_result = await db.execute(income_stmt)
    monthly_income = income_result.scalar() or 0

    return {
        "monthly_income": float(monthly_income),
        "spending": spending,
        "total_monthly_spending": sum(spending.values()),
    }


async def _get_recent_transactions(db: AsyncSession, user_id: UUID, limit: int = 50) -> list:
    """Get recent transactions for context."""
    from sqlalchemy import select, desc, and_
    from app.models.transaction import Transaction

    stmt = (
        select(Transaction)
        .where(
            and_(
                Transaction.user_id == user_id,
                Transaction.deleted_at.is_(None),
            )
        )
        .order_by(desc(Transaction.date))
        .limit(limit)
    )

    result = await db.execute(stmt)
    transactions = result.scalars().all()

    return [
        {
            "description": t.description,
            "amount": float(t.amount),
            "category": t.category,
            "date": t.date.isoformat(),
            "type": t.type.value if hasattr(t.type, "value") else str(t.type),
        }
        for t in transactions
    ]


async def _get_user_goals(db: AsyncSession, user_id: UUID) -> list:
    """Get user's financial goals."""
    from sqlalchemy import select, and_
    from app.models.financial_goal import FinancialGoal

    stmt = select(FinancialGoal).where(
        and_(
            FinancialGoal.user_id == user_id,
            FinancialGoal.status == "ACTIVE",
        )
    )

    result = await db.execute(stmt)
    goals = result.scalars().all()

    return [
        {
            "name": g.name,
            "target": float(g.target_amount),
            "current": float(g.current_amount),
            "deadline": g.deadline.isoformat() if g.deadline else None,
        }
        for g in goals
    ]


# ============================================================================
# FEEDBACK COLLECTION ENDPOINTS
# ============================================================================


class CategoryCorrectionRequest(BaseModel):
    """Request to submit a category correction."""

    user_id: UUID = Field(..., description="User ID")
    transaction_id: UUID = Field(..., description="Transaction ID")
    merchant_raw: str = Field(
        ..., description="Raw merchant description", min_length=1, max_length=500
    )
    original_category: str = Field(..., description="Original category assigned")
    corrected_category: str = Field(..., description="User's corrected category")
    merchant_normalized: Optional[str] = Field(
        None, description="Normalized merchant name if available"
    )


class CategoryCorrectionResponse(BaseModel):
    """Response from category correction submission."""

    status: str
    merchant_key: Optional[str] = None
    auto_updated: bool = False
    consensus_category: Optional[str] = None
    message: str


@router.post("/feedback/correction", response_model=CategoryCorrectionResponse)
@limiter.limit("30/minute", key_func=get_user_or_ip)
async def submit_category_correction(
    request: Request,
    correction_request: CategoryCorrectionRequest,
) -> CategoryCorrectionResponse:
    """
    Submit a category correction for a transaction.

    This feedback is used to:
    - Improve categorization accuracy over time
    - Auto-update the merchant database when consensus is reached
    - Generate training data for model improvements

    Rate limited to 30 requests/minute per user/IP.
    """
    from app.services.feedback_collector import record_category_correction

    try:
        result = await record_category_correction(
            user_id=str(correction_request.user_id),
            transaction_id=str(correction_request.transaction_id),
            merchant_raw=correction_request.merchant_raw,
            original_category=correction_request.original_category,
            corrected_category=correction_request.corrected_category,
            merchant_normalized=correction_request.merchant_normalized,
        )

        message = "Correction recorded"
        if result.get("auto_updated"):
            message = f"Correction recorded. Merchant database updated to '{result['consensus_category']}' based on consensus."
        elif result.get("consensus_category"):
            message = (
                f"Correction recorded. Consensus reached for '{result['consensus_category']}'."
            )

        return CategoryCorrectionResponse(
            status=result["status"],
            merchant_key=result.get("merchant_key"),
            auto_updated=result.get("auto_updated", False),
            consensus_category=result.get("consensus_category"),
            message=message,
        )

    except Exception as e:
        logger.error("Failed to record category correction", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to record correction: {str(e)}")


class FeedbackStatsResponse(BaseModel):
    """Feedback collection statistics."""

    total_corrections: int
    auto_updates_made: int
    unique_merchants_corrected: int
    aggregates_count: int
    pending_consensus: int
    has_consensus: int


@router.get("/feedback/stats", response_model=FeedbackStatsResponse)
@limiter.limit("10/minute")
async def get_feedback_stats(request: Request) -> FeedbackStatsResponse:
    """
    Get feedback collection statistics.

    Returns metrics about collected user corrections and auto-updates.
    """
    from app.services.feedback_collector import get_feedback_collector

    try:
        collector = get_feedback_collector()
        stats = await collector.get_stats()

        return FeedbackStatsResponse(**stats)

    except Exception as e:
        logger.error("Failed to get feedback stats", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")
