import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from decimal import Decimal
from datetime import date

from app.services.transaction_service import TransactionService
from app.schemas.transaction import TransactionCreate, TransactionType, TransactionSource
from app.ml.categorization_engine import CategoryPrediction
from app.services.ai_brain_service import AIBrainResponse, AIBrainMode

@pytest.mark.asyncio
async def test_create_transaction_fallback_to_ai_brain():
    # Setup
    # Use MagicMock for db session because 'add' is sync, but 'flush'/'refresh' are async
    mock_db = MagicMock()
    mock_db.flush = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.execute = AsyncMock()

    # Mock CategorizationEngine
    mock_categorization_engine = AsyncMock()
    # Return low confidence
    mock_categorization_engine.categorize.return_value = CategoryPrediction(
        category="Unsure",
        confidence=0.5,
        model_type="GLOBAL"
    )

    service = TransactionService(mock_db, mock_categorization_engine)

    # Mock AIBrainService
    mock_ai_brain = AsyncMock()
    mock_ai_response = AIBrainResponse(
        mode=AIBrainMode.PARSE,
        response="Parsed",
        parsed_data={"category": "AI Categorized", "confidence": 0.95},
        confidence=0.95
    )
    mock_ai_brain.parse_transaction.return_value = mock_ai_response

    # Transaction data
    user_id = uuid4()
    transaction_data = TransactionCreate(
        amount=Decimal("10.00"),
        date=date.today(),
        description="Ambiguous Transaction",
        type=TransactionType.EXPENSE,
        source=TransactionSource.MANUAL,
        connection_id=None
    )

    # Patch get_ai_brain_service in the module where it is defined
    with patch('app.services.ai_brain_service.get_ai_brain_service', return_value=mock_ai_brain):
        # Mock detect_duplicate to return None
        service.detect_duplicate = AsyncMock(return_value=None)

        # Act
        transaction = await service.create_transaction(
            user_id=user_id,
            transaction_data=transaction_data,
            auto_categorize=True
        )

        # Assert
        assert transaction.category == "AI Categorized"
        assert transaction.confidence_score == 0.95

        # Verify calls
        mock_categorization_engine.categorize.assert_awaited_once()
        mock_ai_brain.parse_transaction.assert_awaited_once()

@pytest.mark.asyncio
async def test_create_transaction_fallback_when_exception():
    # Setup
    mock_db = MagicMock()
    mock_db.flush = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.execute = AsyncMock()

    # Mock CategorizationEngine to raise exception
    mock_categorization_engine = AsyncMock()
    mock_categorization_engine.categorize.side_effect = Exception("Model broken")

    service = TransactionService(mock_db, mock_categorization_engine)

    # Mock AIBrainService
    mock_ai_brain = AsyncMock()
    mock_ai_response = AIBrainResponse(
        mode=AIBrainMode.PARSE,
        response="Parsed",
        parsed_data={"category": "AI Rescued", "confidence": 0.9},
        confidence=0.9
    )
    mock_ai_brain.parse_transaction.return_value = mock_ai_response

    user_id = uuid4()
    transaction_data = TransactionCreate(
        amount=Decimal("10.00"),
        date=date.today(),
        description="Broken Model Transaction",
        type=TransactionType.EXPENSE,
        source=TransactionSource.MANUAL,
        connection_id=None
    )

    with patch('app.services.ai_brain_service.get_ai_brain_service', return_value=mock_ai_brain):
        service.detect_duplicate = AsyncMock(return_value=None)

        # Act
        transaction = await service.create_transaction(
            user_id=user_id,
            transaction_data=transaction_data,
            auto_categorize=True
        )

        # Assert
        assert transaction.category == "AI Rescued"

        # Verify calls
        mock_categorization_engine.categorize.assert_awaited_once()
        mock_ai_brain.parse_transaction.assert_awaited_once()
