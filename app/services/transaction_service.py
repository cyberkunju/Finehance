"""Transaction service for managing financial transactions."""

from datetime import datetime, timedelta, timezone
from datetime import date as date_type
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func, and_, desc, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Transaction
from app.schemas.transaction import (
    TransactionCreate,
    TransactionUpdate,
    TransactionFilters,
    Pagination,
)
from app.ml.categorization_engine import CategorizationEngine
from app.logging_config import get_logger
from app.config import settings

logger = get_logger(__name__)


class TransactionService:
    """Service for managing transactions with CRUD operations and duplicate detection."""

    def __init__(
        self, db: AsyncSession, categorization_engine: Optional[CategorizationEngine] = None
    ):
        """Initialize transaction service.

        Args:
            db: Database session
            categorization_engine: Optional categorization engine for auto-categorization
        """
        self.db = db
        self.categorization_engine = categorization_engine or CategorizationEngine()

    async def create_transaction(
        self,
        user_id: UUID,
        transaction_data: TransactionCreate,
        category: Optional[str] = None,
        confidence_score: Optional[float] = None,
        auto_categorize: bool = True,
    ) -> Transaction:
        """Create a new transaction.

        Args:
            user_id: User ID
            transaction_data: Transaction creation data
            category: Category (if not provided, will auto-categorize if enabled)
            confidence_score: Confidence score for auto-categorization
            auto_categorize: Whether to automatically categorize if no category provided

        Returns:
            Created transaction

        Raises:
            ValueError: If category is not provided and auto-categorization is disabled
        """
        # Use provided category or the one from transaction_data
        final_category = category or transaction_data.category
        final_confidence = confidence_score

        # Auto-categorize if no category provided and auto-categorization is enabled
        if not final_category and auto_categorize:
            model_source = "NONE"
            # Step 1: Try Fast Path (Local ML)
            try:
                prediction = await self.categorization_engine.categorize(
                    description=transaction_data.description,
                    amount=transaction_data.amount,
                    user_id=str(user_id),
                )
                final_category = prediction.category
                final_confidence = prediction.confidence
                model_source = prediction.model_type
            except Exception as e:
                logger.warning(
                    "Local categorization failed, attempting fallback",
                    description=transaction_data.description,
                    error=str(e),
                )
                final_confidence = 0.0

            # Step 2: Try Smart Path (AI Brain) if confidence is low
            # Use configurable threshold from settings
            confidence_threshold = settings.ai_brain_fallback_threshold

            if final_confidence < confidence_threshold:
                try:
                    # Lazy import to avoid circular dependencies
                    from app.services.ai_brain_service import get_ai_brain_service

                    logger.info(
                        "Low confidence in local model, invoking AI Brain",
                        local_confidence=final_confidence,
                        description=transaction_data.description,
                    )

                    ai_brain = get_ai_brain_service()
                    # Use parse_transaction which includes RAG
                    ai_response = await ai_brain.parse_transaction(
                        description=transaction_data.description,
                        user_context={"user_id": str(user_id)},
                    )

                    if ai_response.parsed_data and ai_response.parsed_data.get("category"):
                        final_category = ai_response.parsed_data["category"]
                        final_confidence = ai_response.confidence
                        model_source = "AI_BRAIN"

                        logger.info(
                            "Transaction categorized by AI Brain",
                            category=final_category,
                            confidence=final_confidence,
                            rag_corrected=ai_response.parsed_data.get("rag_corrected", False),
                        )
                except Exception as e:
                    logger.error(
                        "AI Brain fallback failed",
                        description=transaction_data.description,
                        error=str(e),
                    )

            if final_category and model_source != "NONE" and model_source != "AI_BRAIN":
                logger.info(
                    "Transaction auto-categorized by local model",
                    description=transaction_data.description,
                    category=final_category,
                    confidence=final_confidence,
                    model_type=model_source,
                )

        if not final_category:
            # Fallback to "Uncategorized" if auto-categorization fails
            final_category = "Uncategorized"

        # Check for duplicates
        duplicate = await self.detect_duplicate(
            user_id=user_id,
            amount=transaction_data.amount,
            date=transaction_data.date,
            description=transaction_data.description,
        )

        if duplicate:
            logger.warning(
                "Duplicate transaction detected",
                user_id=str(user_id),
                amount=str(transaction_data.amount),
                date=str(transaction_data.date),
                duplicate_id=str(duplicate.id),
            )
            # Return existing transaction instead of creating duplicate
            return duplicate

        # Create new transaction
        transaction = Transaction(
            user_id=user_id,
            amount=transaction_data.amount,
            date=transaction_data.date,
            description=transaction_data.description,
            category=final_category,
            type=transaction_data.type.value,
            source=transaction_data.source.value,
            confidence_score=final_confidence,
            connection_id=transaction_data.connection_id,
        )

        self.db.add(transaction)
        await self.db.flush()
        await self.db.refresh(transaction)

        logger.info(
            "Transaction created",
            transaction_id=str(transaction.id),
            user_id=str(user_id),
            amount=str(transaction.amount),
            category=transaction.category,
            type=transaction.type,
            confidence_score=final_confidence,
        )

        return transaction

    async def get_transaction(
        self,
        transaction_id: UUID,
        user_id: UUID,
    ) -> Optional[Transaction]:
        """Get a transaction by ID.

        Args:
            transaction_id: Transaction ID
            user_id: User ID (for authorization)

        Returns:
            Transaction if found and belongs to user, None otherwise
        """
        stmt = select(Transaction).where(
            and_(
                Transaction.id == transaction_id,
                Transaction.user_id == user_id,
                Transaction.deleted_at.is_(None),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_transaction(
        self,
        transaction_id: UUID,
        user_id: UUID,
        updates: TransactionUpdate,
    ) -> Optional[Transaction]:
        """Update an existing transaction.

        Args:
            transaction_id: Transaction ID
            user_id: User ID (for authorization)
            updates: Fields to update

        Returns:
            Updated transaction if found, None otherwise
        """
        # Get existing transaction
        transaction = await self.get_transaction(transaction_id, user_id)
        if not transaction:
            logger.warning(
                "Transaction not found for update",
                transaction_id=str(transaction_id),
                user_id=str(user_id),
            )
            return None

        # Update fields
        update_data = updates.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field == "type" and value is not None:
                setattr(transaction, field, value.value)
            else:
                setattr(transaction, field, value)

        transaction.updated_at = datetime.utcnow()
        await self.db.flush()
        await self.db.refresh(transaction)

        logger.info(
            "Transaction updated",
            transaction_id=str(transaction_id),
            user_id=str(user_id),
            updated_fields=list(update_data.keys()),
        )

        return transaction

    async def delete_transaction(
        self,
        transaction_id: UUID,
        user_id: UUID,
    ) -> bool:
        """Soft delete a transaction.

        Args:
            transaction_id: Transaction ID
            user_id: User ID (for authorization)

        Returns:
            True if deleted, False if not found
        """
        transaction = await self.get_transaction(transaction_id, user_id)
        if not transaction:
            logger.warning(
                "Transaction not found for deletion",
                transaction_id=str(transaction_id),
                user_id=str(user_id),
            )
            return False

        # Soft delete
        transaction.deleted_at = datetime.utcnow()
        await self.db.flush()

        logger.info(
            "Transaction deleted",
            transaction_id=str(transaction_id),
            user_id=str(user_id),
        )

        return True

    async def list_transactions(
        self,
        user_id: UUID,
        filters: Optional[TransactionFilters] = None,
        pagination: Optional[Pagination] = None,
    ) -> tuple[list[Transaction], int]:
        """List transactions with filtering and pagination.

        Args:
            user_id: User ID
            filters: Optional filters
            pagination: Optional pagination parameters

        Returns:
            Tuple of (transactions list, total count)
        """
        # Base query
        stmt = select(Transaction).where(
            and_(
                Transaction.user_id == user_id,
                Transaction.deleted_at.is_(None),
            )
        )

        # Apply filters
        if filters:
            if filters.start_date:
                stmt = stmt.where(Transaction.date >= filters.start_date)
            if filters.end_date:
                stmt = stmt.where(Transaction.date <= filters.end_date)
            if filters.category:
                stmt = stmt.where(Transaction.category == filters.category)
            if filters.type:
                stmt = stmt.where(Transaction.type == filters.type.value)
            if filters.min_amount is not None:
                stmt = stmt.where(Transaction.amount >= filters.min_amount)
            if filters.max_amount is not None:
                stmt = stmt.where(Transaction.amount <= filters.max_amount)
            if filters.search:
                # Case-insensitive search in description
                search_pattern = f"%{filters.search}%"
                stmt = stmt.where(Transaction.description.ilike(search_pattern))

        # Get total count before pagination
        # Optimize count query by avoiding subquery: SELECT count(*) FROM table WHERE ...
        count_stmt = stmt.with_only_columns(func.count()).order_by(None)
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar_one()

        # Sort by date descending (newest first) - Requirement 1.2
        stmt = stmt.order_by(desc(Transaction.date), desc(Transaction.created_at))

        # Apply pagination
        if pagination:
            stmt = stmt.offset(pagination.offset).limit(pagination.page_size)

        # Execute query
        result = await self.db.execute(stmt)
        transactions = list(result.scalars().all())

        logger.debug(
            "Transactions listed",
            user_id=str(user_id),
            count=len(transactions),
            total=total,
        )

        return transactions, total

    async def detect_duplicate(
        self,
        user_id: UUID,
        amount: Decimal,
        date: date_type,
        description: str,
    ) -> Optional[Transaction]:
        """Detect duplicate transaction within 24-hour window.

        According to Requirements 4.4 and 13.4, duplicates are detected based on
        matching date, amount, and description within a 24-hour window.

        Args:
            user_id: User ID
            amount: Transaction amount
            date: Transaction date
            description: Transaction description

        Returns:
            Existing transaction if duplicate found, None otherwise
        """
        # Define 24-hour window around the transaction date
        start_date = date - timedelta(days=1)
        end_date = date + timedelta(days=1)

        # Query for matching transactions
        stmt = select(Transaction).where(
            and_(
                Transaction.user_id == user_id,
                Transaction.amount == amount,
                Transaction.date >= start_date,
                Transaction.date <= end_date,
                Transaction.description == description,
                Transaction.deleted_at.is_(None),
            )
        )

        result = await self.db.execute(stmt)
        duplicate = result.scalar_one_or_none()

        if duplicate:
            logger.debug(
                "Duplicate transaction found",
                user_id=str(user_id),
                amount=str(amount),
                date=str(date),
                duplicate_id=str(duplicate.id),
            )

        return duplicate

    async def search_transactions(
        self,
        user_id: UUID,
        search_query: str,
        pagination: Optional[Pagination] = None,
    ) -> tuple[list[Transaction], int]:
        """Search transactions by description.

        Args:
            user_id: User ID
            search_query: Search query string
            pagination: Optional pagination parameters

        Returns:
            Tuple of (matching transactions, total count)
        """
        filters = TransactionFilters(search=search_query)
        return await self.list_transactions(user_id, filters, pagination)

    async def count_transactions(self, user_id: UUID) -> int:
        """Count total transactions for a user.

        Args:
            user_id: User ID

        Returns:
            Total number of non-deleted transactions
        """
        stmt = (
            select(func.count())
            .select_from(Transaction)
            .where(
                and_(
                    Transaction.user_id == user_id,
                    Transaction.deleted_at.is_(None),
                )
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def delete_all_transactions(self, user_id: UUID) -> int:
        """Delete all transactions for a user.

        Args:
            user_id: User ID

        Returns:
            Number of deleted transactions
        """
        stmt = (
            update(Transaction)
            .where(
                and_(
                    Transaction.user_id == user_id,
                    Transaction.deleted_at.is_(None),
                )
            )
            .values(deleted_at=datetime.utcnow())
        )
        result = await self.db.execute(stmt)
        await self.db.flush()

        logger.info(
            "All transactions deleted for user",
            user_id=str(user_id),
            count=result.rowcount,
        )

        return result.rowcount
