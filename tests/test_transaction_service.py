"""Unit tests for Transaction Service."""

import pytest
from datetime import timedelta
from datetime import date as date_type
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.transaction_service import TransactionService
from app.ml.categorization_engine import CategorizationEngine
from app.schemas.transaction import (
    TransactionCreate,
    TransactionUpdate,
    TransactionFilters,
    Pagination,
    TransactionType,
    TransactionSource,
)


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        email="test@example.com",
        password_hash="hashed_password",
        first_name="Test",
        last_name="User",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def transaction_service(db_session: AsyncSession) -> TransactionService:
    """Create transaction service instance with categorization engine."""
    categorization_engine = CategorizationEngine()
    return TransactionService(db_session, categorization_engine)


class TestCreateTransaction:
    """Tests for creating transactions."""

    async def test_create_transaction_success(
        self,
        transaction_service: TransactionService,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test successful transaction creation."""
        transaction_data = TransactionCreate(
            amount=Decimal("100.50"),
            date=date_type.today(),
            description="Test transaction",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL,
        )

        transaction = await transaction_service.create_transaction(
            user_id=test_user.id,
            transaction_data=transaction_data,
            category="Groceries",
        )
        await db_session.commit()

        assert transaction.id is not None
        assert transaction.user_id == test_user.id
        assert transaction.amount == Decimal("100.50")
        assert transaction.description == "Test transaction"
        assert transaction.category == "Groceries"
        assert transaction.type == "EXPENSE"
        assert transaction.source == "MANUAL"
        assert transaction.deleted_at is None

    async def test_create_transaction_with_category_in_data(
        self,
        transaction_service: TransactionService,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test transaction creation with category in transaction_data."""
        transaction_data = TransactionCreate(
            amount=Decimal("50.00"),
            date=date_type.today(),
            description="Grocery shopping",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL,
            category="Groceries",
        )

        transaction = await transaction_service.create_transaction(
            user_id=test_user.id,
            transaction_data=transaction_data,
        )
        await db_session.commit()

        assert transaction.category == "Groceries"

    async def test_create_transaction_without_category_auto_categorizes(
        self,
        transaction_service: TransactionService,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test that creating transaction without category auto-categorizes."""
        transaction_data = TransactionCreate(
            amount=Decimal("50.00"),
            date=date_type.today(),
            description="Whole Foods Market",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL,
        )

        # Should auto-categorize instead of raising error
        transaction = await transaction_service.create_transaction(
            user_id=test_user.id,
            transaction_data=transaction_data,
        )
        await db_session.commit()

        assert transaction.category == "Groceries"
        assert transaction.confidence_score is not None

    async def test_create_transaction_with_confidence_score(
        self,
        transaction_service: TransactionService,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test transaction creation with confidence score."""
        transaction_data = TransactionCreate(
            amount=Decimal("75.25"),
            date=date_type.today(),
            description="Auto-categorized transaction",
            type=TransactionType.EXPENSE,
            source=TransactionSource.API,
        )

        transaction = await transaction_service.create_transaction(
            user_id=test_user.id,
            transaction_data=transaction_data,
            category="Dining",
            confidence_score=0.85,
        )
        await db_session.commit()

        assert transaction.confidence_score == 0.85


class TestGetTransaction:
    """Tests for retrieving transactions."""

    async def test_get_existing_transaction(
        self,
        transaction_service: TransactionService,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test retrieving an existing transaction."""
        # Create transaction
        transaction_data = TransactionCreate(
            amount=Decimal("100.00"),
            date=date_type.today(),
            description="Test",
            type=TransactionType.INCOME,
            source=TransactionSource.MANUAL,
        )
        created = await transaction_service.create_transaction(
            user_id=test_user.id,
            transaction_data=transaction_data,
            category="Salary",
        )
        await db_session.commit()

        # Retrieve transaction
        retrieved = await transaction_service.get_transaction(
            transaction_id=created.id,
            user_id=test_user.id,
        )

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.amount == Decimal("100.00")

    async def test_get_nonexistent_transaction(
        self,
        transaction_service: TransactionService,
        test_user: User,
    ):
        """Test retrieving a non-existent transaction returns None."""
        result = await transaction_service.get_transaction(
            transaction_id=uuid4(),
            user_id=test_user.id,
        )
        assert result is None

    async def test_get_transaction_wrong_user(
        self,
        transaction_service: TransactionService,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test that user cannot access another user's transaction."""
        # Create transaction
        transaction_data = TransactionCreate(
            amount=Decimal("100.00"),
            date=date_type.today(),
            description="Test",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL,
        )
        created = await transaction_service.create_transaction(
            user_id=test_user.id,
            transaction_data=transaction_data,
            category="Shopping",
        )
        await db_session.commit()

        # Try to retrieve with different user ID
        result = await transaction_service.get_transaction(
            transaction_id=created.id,
            user_id=uuid4(),
        )
        assert result is None


class TestUpdateTransaction:
    """Tests for updating transactions."""

    async def test_update_transaction_amount(
        self,
        transaction_service: TransactionService,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test updating transaction amount."""
        # Create transaction
        transaction_data = TransactionCreate(
            amount=Decimal("100.00"),
            date=date_type.today(),
            description="Original",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL,
        )
        created = await transaction_service.create_transaction(
            user_id=test_user.id,
            transaction_data=transaction_data,
            category="Shopping",
        )
        await db_session.commit()

        # Update amount
        updates = TransactionUpdate(amount=Decimal("150.00"))
        updated = await transaction_service.update_transaction(
            transaction_id=created.id,
            user_id=test_user.id,
            updates=updates,
        )
        await db_session.commit()

        assert updated is not None
        assert updated.amount == Decimal("150.00")
        assert updated.description == "Original"  # Unchanged

    async def test_update_multiple_fields(
        self,
        transaction_service: TransactionService,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test updating multiple transaction fields."""
        # Create transaction
        transaction_data = TransactionCreate(
            amount=Decimal("100.00"),
            date=date_type.today(),
            description="Original",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL,
        )
        created = await transaction_service.create_transaction(
            user_id=test_user.id,
            transaction_data=transaction_data,
            category="Shopping",
        )
        await db_session.commit()

        # Update multiple fields
        new_date = date_type.today() - timedelta(days=1)
        updates = TransactionUpdate(
            amount=Decimal("200.00"),
            description="Updated description",
            date=new_date,
            category="Groceries",
        )
        updated = await transaction_service.update_transaction(
            transaction_id=created.id,
            user_id=test_user.id,
            updates=updates,
        )
        await db_session.commit()

        assert updated.amount == Decimal("200.00")
        assert updated.description == "Updated description"
        assert updated.date == new_date
        assert updated.category == "Groceries"

    async def test_update_nonexistent_transaction(
        self,
        transaction_service: TransactionService,
        test_user: User,
    ):
        """Test updating non-existent transaction returns None."""
        updates = TransactionUpdate(amount=Decimal("100.00"))
        result = await transaction_service.update_transaction(
            transaction_id=uuid4(),
            user_id=test_user.id,
            updates=updates,
        )
        assert result is None


class TestDeleteTransaction:
    """Tests for deleting transactions."""

    async def test_delete_transaction_success(
        self,
        transaction_service: TransactionService,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test successful transaction deletion (soft delete)."""
        # Create transaction
        transaction_data = TransactionCreate(
            amount=Decimal("100.00"),
            date=date_type.today(),
            description="To be deleted",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL,
        )
        created = await transaction_service.create_transaction(
            user_id=test_user.id,
            transaction_data=transaction_data,
            category="Shopping",
        )
        await db_session.commit()

        # Delete transaction
        result = await transaction_service.delete_transaction(
            transaction_id=created.id,
            user_id=test_user.id,
        )
        await db_session.commit()

        assert result is True

        # Verify transaction is soft deleted
        deleted = await transaction_service.get_transaction(
            transaction_id=created.id,
            user_id=test_user.id,
        )
        assert deleted is None

    async def test_delete_nonexistent_transaction(
        self,
        transaction_service: TransactionService,
        test_user: User,
    ):
        """Test deleting non-existent transaction returns False."""
        result = await transaction_service.delete_transaction(
            transaction_id=uuid4(),
            user_id=test_user.id,
        )
        assert result is False


class TestListTransactions:
    """Tests for listing transactions."""

    async def test_list_transactions_empty(
        self,
        transaction_service: TransactionService,
        test_user: User,
    ):
        """Test listing transactions when none exist."""
        transactions, total = await transaction_service.list_transactions(
            user_id=test_user.id,
        )
        assert transactions == []
        assert total == 0

    async def test_list_transactions_sorted_by_date(
        self,
        transaction_service: TransactionService,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test that transactions are sorted by date descending (newest first)."""
        # Create transactions with different dates
        dates = [
            date_type.today() - timedelta(days=2),
            date_type.today(),
            date_type.today() - timedelta(days=1),
        ]

        for i, trans_date in enumerate(dates):
            transaction_data = TransactionCreate(
                amount=Decimal("100.00"),
                date=trans_date,
                description=f"Transaction {i}",
                type=TransactionType.EXPENSE,
                source=TransactionSource.MANUAL,
            )
            await transaction_service.create_transaction(
                user_id=test_user.id,
                transaction_data=transaction_data,
                category="Shopping",
            )
        await db_session.commit()

        # List transactions
        transactions, total = await transaction_service.list_transactions(
            user_id=test_user.id,
        )

        assert total == 3
        assert len(transactions) == 3
        # Verify descending order (newest first)
        assert transactions[0].date == date_type.today()
        assert transactions[1].date == date_type.today() - timedelta(days=1)
        assert transactions[2].date == date_type.today() - timedelta(days=2)

    async def test_list_transactions_with_pagination(
        self,
        transaction_service: TransactionService,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test pagination of transaction list."""
        # Create 5 transactions
        for i in range(5):
            transaction_data = TransactionCreate(
                amount=Decimal(f"{100 + i}.00"),
                date=date_type.today(),
                description=f"Transaction {i}",
                type=TransactionType.EXPENSE,
                source=TransactionSource.MANUAL,
            )
            await transaction_service.create_transaction(
                user_id=test_user.id,
                transaction_data=transaction_data,
                category="Shopping",
            )
        await db_session.commit()

        # Get first page (2 items)
        pagination = Pagination(page=1, page_size=2)
        transactions, total = await transaction_service.list_transactions(
            user_id=test_user.id,
            pagination=pagination,
        )

        assert total == 5
        assert len(transactions) == 2

        # Get second page
        pagination = Pagination(page=2, page_size=2)
        transactions, total = await transaction_service.list_transactions(
            user_id=test_user.id,
            pagination=pagination,
        )

        assert total == 5
        assert len(transactions) == 2

    async def test_list_transactions_filter_by_date_range(
        self,
        transaction_service: TransactionService,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test filtering transactions by date range."""
        # Create transactions with different dates
        dates = [
            date_type.today() - timedelta(days=10),
            date_type.today() - timedelta(days=5),
            date_type.today(),
        ]

        for trans_date in dates:
            transaction_data = TransactionCreate(
                amount=Decimal("100.00"),
                date=trans_date,
                description="Test",
                type=TransactionType.EXPENSE,
                source=TransactionSource.MANUAL,
            )
            await transaction_service.create_transaction(
                user_id=test_user.id,
                transaction_data=transaction_data,
                category="Shopping",
            )
        await db_session.commit()

        # Filter by date range
        filters = TransactionFilters(
            start_date=date_type.today() - timedelta(days=7),
            end_date=date_type.today(),
        )
        transactions, total = await transaction_service.list_transactions(
            user_id=test_user.id,
            filters=filters,
        )

        assert total == 2  # Only last 2 transactions

    async def test_list_transactions_filter_by_category(
        self,
        transaction_service: TransactionService,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test filtering transactions by category."""
        # Create transactions with different categories and amounts to avoid duplicate detection
        test_data = [
            ("Groceries", Decimal("100.00")),
            ("Dining", Decimal("150.00")),
            ("Groceries", Decimal("200.00")),
        ]

        for category, amount in test_data:
            transaction_data = TransactionCreate(
                amount=amount,
                date=date_type.today(),
                description="Test",
                type=TransactionType.EXPENSE,
                source=TransactionSource.MANUAL,
            )
            await transaction_service.create_transaction(
                user_id=test_user.id,
                transaction_data=transaction_data,
                category=category,
            )
        await db_session.commit()

        # Filter by category
        filters = TransactionFilters(category="Groceries")
        transactions, total = await transaction_service.list_transactions(
            user_id=test_user.id,
            filters=filters,
        )

        assert total == 2
        assert all(t.category == "Groceries" for t in transactions)

    async def test_list_transactions_filter_by_type(
        self,
        transaction_service: TransactionService,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test filtering transactions by type."""
        # Create income and expense transactions with different amounts to avoid duplicate detection
        test_data = [
            (TransactionType.INCOME, Decimal("100.00")),
            (TransactionType.EXPENSE, Decimal("150.00")),
            (TransactionType.INCOME, Decimal("200.00")),
        ]

        for trans_type, amount in test_data:
            transaction_data = TransactionCreate(
                amount=amount,
                date=date_type.today(),
                description="Test",
                type=trans_type,
                source=TransactionSource.MANUAL,
            )
            await transaction_service.create_transaction(
                user_id=test_user.id,
                transaction_data=transaction_data,
                category="Salary" if trans_type == TransactionType.INCOME else "Shopping",
            )
        await db_session.commit()

        # Filter by type
        filters = TransactionFilters(type=TransactionType.INCOME)
        transactions, total = await transaction_service.list_transactions(
            user_id=test_user.id,
            filters=filters,
        )

        assert total == 2
        assert all(t.type == "INCOME" for t in transactions)

    async def test_list_transactions_filter_by_amount_range(
        self,
        transaction_service: TransactionService,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test filtering transactions by amount range."""
        # Create transactions with different amounts
        amounts = [Decimal("50.00"), Decimal("100.00"), Decimal("150.00")]

        for amount in amounts:
            transaction_data = TransactionCreate(
                amount=amount,
                date=date_type.today(),
                description="Test",
                type=TransactionType.EXPENSE,
                source=TransactionSource.MANUAL,
            )
            await transaction_service.create_transaction(
                user_id=test_user.id,
                transaction_data=transaction_data,
                category="Shopping",
            )
        await db_session.commit()

        # Filter by amount range
        filters = TransactionFilters(
            min_amount=Decimal("75.00"),
            max_amount=Decimal("125.00"),
        )
        transactions, total = await transaction_service.list_transactions(
            user_id=test_user.id,
            filters=filters,
        )

        assert total == 1
        assert transactions[0].amount == Decimal("100.00")

    async def test_list_transactions_search_description(
        self,
        transaction_service: TransactionService,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test searching transactions by description."""
        # Create transactions with different descriptions
        descriptions = ["Walmart Groceries", "Target Shopping", "Whole Foods"]

        for desc in descriptions:
            transaction_data = TransactionCreate(
                amount=Decimal("100.00"),
                date=date_type.today(),
                description=desc,
                type=TransactionType.EXPENSE,
                source=TransactionSource.MANUAL,
            )
            await transaction_service.create_transaction(
                user_id=test_user.id,
                transaction_data=transaction_data,
                category="Shopping",
            )
        await db_session.commit()

        # Search for "walmart"
        filters = TransactionFilters(search="walmart")
        transactions, total = await transaction_service.list_transactions(
            user_id=test_user.id,
            filters=filters,
        )

        assert total == 1
        assert "Walmart" in transactions[0].description


class TestDuplicateDetection:
    """Tests for duplicate transaction detection."""

    async def test_detect_duplicate_exact_match(
        self,
        transaction_service: TransactionService,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test detecting exact duplicate transaction."""
        # Create original transaction
        transaction_data = TransactionCreate(
            amount=Decimal("100.00"),
            date=date_type.today(),
            description="Walmart Purchase",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL,
        )
        original = await transaction_service.create_transaction(
            user_id=test_user.id,
            transaction_data=transaction_data,
            category="Shopping",
        )
        await db_session.commit()

        # Try to detect duplicate
        duplicate = await transaction_service.detect_duplicate(
            user_id=test_user.id,
            amount=Decimal("100.00"),
            date=date_type.today(),
            description="Walmart Purchase",
        )

        assert duplicate is not None
        assert duplicate.id == original.id

    async def test_detect_duplicate_within_24_hours(
        self,
        transaction_service: TransactionService,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test detecting duplicate within 24-hour window."""
        # Create original transaction
        original_date = date_type.today() - timedelta(days=1)
        transaction_data = TransactionCreate(
            amount=Decimal("100.00"),
            date=original_date,
            description="Walmart Purchase",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL,
        )
        original = await transaction_service.create_transaction(
            user_id=test_user.id,
            transaction_data=transaction_data,
            category="Shopping",
        )
        await db_session.commit()

        # Try to detect duplicate with date within 24 hours
        duplicate = await transaction_service.detect_duplicate(
            user_id=test_user.id,
            amount=Decimal("100.00"),
            date=date_type.today(),  # Next day
            description="Walmart Purchase",
        )

        assert duplicate is not None
        assert duplicate.id == original.id

    async def test_no_duplicate_different_amount(
        self,
        transaction_service: TransactionService,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test that different amount is not detected as duplicate."""
        # Create original transaction
        transaction_data = TransactionCreate(
            amount=Decimal("100.00"),
            date=date_type.today(),
            description="Walmart Purchase",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL,
        )
        await transaction_service.create_transaction(
            user_id=test_user.id,
            transaction_data=transaction_data,
            category="Shopping",
        )
        await db_session.commit()

        # Try to detect duplicate with different amount
        duplicate = await transaction_service.detect_duplicate(
            user_id=test_user.id,
            amount=Decimal("150.00"),  # Different amount
            date=date_type.today(),
            description="Walmart Purchase",
        )

        assert duplicate is None

    async def test_no_duplicate_different_description(
        self,
        transaction_service: TransactionService,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test that different description is not detected as duplicate."""
        # Create original transaction
        transaction_data = TransactionCreate(
            amount=Decimal("100.00"),
            date=date_type.today(),
            description="Walmart Purchase",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL,
        )
        await transaction_service.create_transaction(
            user_id=test_user.id,
            transaction_data=transaction_data,
            category="Shopping",
        )
        await db_session.commit()

        # Try to detect duplicate with different description
        duplicate = await transaction_service.detect_duplicate(
            user_id=test_user.id,
            amount=Decimal("100.00"),
            date=date_type.today(),
            description="Target Purchase",  # Different description
        )

        assert duplicate is None

    async def test_no_duplicate_outside_24_hour_window(
        self,
        transaction_service: TransactionService,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test that transaction outside 24-hour window is not detected as duplicate."""
        # Create original transaction
        original_date = date_type.today() - timedelta(days=3)
        transaction_data = TransactionCreate(
            amount=Decimal("100.00"),
            date=original_date,
            description="Walmart Purchase",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL,
        )
        await transaction_service.create_transaction(
            user_id=test_user.id,
            transaction_data=transaction_data,
            category="Shopping",
        )
        await db_session.commit()

        # Try to detect duplicate outside 24-hour window
        duplicate = await transaction_service.detect_duplicate(
            user_id=test_user.id,
            amount=Decimal("100.00"),
            date=date_type.today(),  # 3 days later
            description="Walmart Purchase",
        )

        assert duplicate is None

    async def test_create_transaction_prevents_duplicate(
        self,
        transaction_service: TransactionService,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test that create_transaction prevents creating duplicates."""
        # Create original transaction
        transaction_data = TransactionCreate(
            amount=Decimal("100.00"),
            date=date_type.today(),
            description="Walmart Purchase",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL,
        )
        original = await transaction_service.create_transaction(
            user_id=test_user.id,
            transaction_data=transaction_data,
            category="Shopping",
        )
        await db_session.commit()

        # Try to create duplicate
        duplicate_attempt = await transaction_service.create_transaction(
            user_id=test_user.id,
            transaction_data=transaction_data,
            category="Shopping",
        )
        await db_session.commit()

        # Should return the original transaction, not create a new one
        assert duplicate_attempt.id == original.id

        # Verify only one transaction exists
        transactions, total = await transaction_service.list_transactions(
            user_id=test_user.id,
        )
        assert total == 1


class TestCountTransactions:
    """Tests for counting transactions."""

    async def test_count_transactions_empty(
        self,
        transaction_service: TransactionService,
        test_user: User,
    ):
        """Test counting when no transactions exist."""
        count = await transaction_service.count_transactions(test_user.id)
        assert count == 0

    async def test_count_transactions(
        self,
        transaction_service: TransactionService,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test counting transactions."""
        # Create 3 transactions
        for i in range(3):
            transaction_data = TransactionCreate(
                amount=Decimal("100.00"),
                date=date_type.today(),
                description=f"Transaction {i}",
                type=TransactionType.EXPENSE,
                source=TransactionSource.MANUAL,
            )
            await transaction_service.create_transaction(
                user_id=test_user.id,
                transaction_data=transaction_data,
                category="Shopping",
            )
        await db_session.commit()

        count = await transaction_service.count_transactions(test_user.id)
        assert count == 3

    async def test_count_excludes_deleted_transactions(
        self,
        transaction_service: TransactionService,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test that count excludes soft-deleted transactions."""
        # Create 3 transactions
        transaction_ids = []
        for i in range(3):
            transaction_data = TransactionCreate(
                amount=Decimal("100.00"),
                date=date_type.today(),
                description=f"Transaction {i}",
                type=TransactionType.EXPENSE,
                source=TransactionSource.MANUAL,
            )
            trans = await transaction_service.create_transaction(
                user_id=test_user.id,
                transaction_data=transaction_data,
                category="Shopping",
            )
            transaction_ids.append(trans.id)
        await db_session.commit()

        # Delete one transaction
        await transaction_service.delete_transaction(
            transaction_id=transaction_ids[0],
            user_id=test_user.id,
        )
        await db_session.commit()

        # Count should be 2
        count = await transaction_service.count_transactions(test_user.id)
        assert count == 2


class TestAutoCategorization:
    """Tests for automatic transaction categorization."""

    async def test_auto_categorize_groceries(
        self,
        transaction_service: TransactionService,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test auto-categorization of grocery transaction."""
        transaction_data = TransactionCreate(
            amount=Decimal("50.00"),
            date=date_type.today(),
            description="Whole Foods Market",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL,
            # No category provided - should auto-categorize
        )

        transaction = await transaction_service.create_transaction(
            user_id=test_user.id,
            transaction_data=transaction_data,
        )
        await db_session.commit()

        assert transaction.category == "Groceries"
        assert transaction.confidence_score is not None
        assert transaction.confidence_score > 0.5

    async def test_auto_categorize_dining(
        self,
        transaction_service: TransactionService,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test auto-categorization of dining transaction."""
        transaction_data = TransactionCreate(
            amount=Decimal("25.00"),
            date=date_type.today(),
            description="Starbucks Coffee",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL,
        )

        transaction = await transaction_service.create_transaction(
            user_id=test_user.id,
            transaction_data=transaction_data,
        )
        await db_session.commit()

        assert transaction.category == "Dining"
        assert transaction.confidence_score is not None

    async def test_auto_categorize_transportation(
        self,
        transaction_service: TransactionService,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test auto-categorization of transportation transaction."""
        transaction_data = TransactionCreate(
            amount=Decimal("45.00"),
            date=date_type.today(),
            description="Shell Gas Station",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL,
        )

        transaction = await transaction_service.create_transaction(
            user_id=test_user.id,
            transaction_data=transaction_data,
        )
        await db_session.commit()

        assert transaction.category == "Transportation"
        assert transaction.confidence_score is not None

    async def test_manual_category_overrides_auto(
        self,
        transaction_service: TransactionService,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test that manually provided category overrides auto-categorization."""
        transaction_data = TransactionCreate(
            amount=Decimal("50.00"),
            date=date_type.today(),
            description="Whole Foods Market",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL,
            category="Shopping",  # Manual override
        )

        transaction = await transaction_service.create_transaction(
            user_id=test_user.id,
            transaction_data=transaction_data,
        )
        await db_session.commit()

        # Should use manual category, not auto-categorized "Groceries"
        assert transaction.category == "Shopping"
        assert transaction.confidence_score is None  # No auto-categorization

    async def test_auto_categorize_disabled(
        self,
        transaction_service: TransactionService,
        test_user: User,
    ):
        """Test that error is raised when auto-categorization is disabled and no category provided."""
        transaction_data = TransactionCreate(
            amount=Decimal("50.00"),
            date=date_type.today(),
            description="Unknown Merchant",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL,
        )

        with pytest.raises(ValueError, match="Category must be provided"):
            await transaction_service.create_transaction(
                user_id=test_user.id,
                transaction_data=transaction_data,
                auto_categorize=False,  # Disable auto-categorization
            )

    async def test_auto_categorize_multiple_transactions(
        self,
        transaction_service: TransactionService,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test auto-categorization of multiple transactions."""
        test_cases = [
            ("Amazon Purchase", "Shopping"),
            ("Netflix Subscription", "Entertainment"),
            ("Electric Bill", "Utilities"),
            ("CVS Pharmacy", "Healthcare"),
            ("Payroll Deposit", "Salary"),
        ]

        for description, expected_category in test_cases:
            transaction_data = TransactionCreate(
                amount=Decimal("100.00"),
                date=date_type.today(),
                description=description,
                type=TransactionType.EXPENSE
                if expected_category != "Salary"
                else TransactionType.INCOME,
                source=TransactionSource.MANUAL,
            )

            transaction = await transaction_service.create_transaction(
                user_id=test_user.id,
                transaction_data=transaction_data,
            )
            await db_session.commit()

            assert transaction.category == expected_category, (
                f"Expected {expected_category} for '{description}', got {transaction.category}"
            )
            assert transaction.confidence_score is not None
