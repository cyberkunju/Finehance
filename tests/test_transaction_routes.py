"""Tests for transaction API endpoints."""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from httpx import AsyncClient
from uuid import uuid4

from app.main import app
from app.models.transaction import Transaction
from app.schemas.transaction import TransactionType, TransactionSource, TransactionCreate


async def create_test_transaction(service, user_id, **kwargs):
    """Helper to create a test transaction."""
    defaults = {
        "amount": Decimal("100.00"),
        "date": datetime.now().date(),
        "description": "Test transaction",
        "type": TransactionType.EXPENSE,
        "source": TransactionSource.MANUAL
    }
    defaults.update(kwargs)
    
    transaction_data = TransactionCreate(**defaults)
    return await service.create_transaction(
        user_id=user_id,
        transaction_data=transaction_data
    )


@pytest.mark.asyncio
class TestTransactionRoutes:
    """Test transaction API endpoints."""
    
    async def test_create_transaction_success(self, async_client: AsyncClient, test_user, test_db):
        """Test successful transaction creation."""
        user_id = test_user.id
        
        response = await async_client.post(
            f"/api/transactions?user_id={user_id}",
            json={
                "amount": "100.50",
                "date": "2024-01-15",
                "description": "Grocery shopping",
                "type": "EXPENSE"
            }
        )
        
        if response.status_code != 201:
            print(f"Error response: {response.json()}")
        
        assert response.status_code == 201
        data = response.json()
        assert data["amount"] == "100.50"
        assert data["description"] == "Grocery shopping"
        assert data["type"] == "EXPENSE"
        assert data["source"] == "MANUAL"
        assert "id" in data
        assert "category" in data
        data = response.json()
        assert data["amount"] == "100.50"
        assert data["description"] == "Grocery shopping"
        assert data["type"] == "EXPENSE"
        assert data["source"] == "MANUAL"
        assert "id" in data
        assert "category" in data
    
    async def test_create_transaction_with_category(self, async_client: AsyncClient, test_user, test_db):
        """Test transaction creation with category override."""
        user_id = test_user.id
        
        response = await async_client.post(
            f"/api/transactions?user_id={user_id}",
            json={
                "amount": "50.00",
                "date": "2024-01-15",
                "description": "Coffee",
                "type": "EXPENSE",
                "category": "Dining"
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["category"] == "Dining"
    
    async def test_create_transaction_invalid_amount(self, async_client: AsyncClient, test_user, test_db):
        """Test transaction creation with invalid amount."""
        user_id = test_user.id
        
        response = await async_client.post(
            f"/api/transactions?user_id={user_id}",
            json={
                "amount": "-50.00",
                "date": "2024-01-15",
                "description": "Invalid",
                "type": "EXPENSE"
            }
        )
        
        assert response.status_code == 422  # Validation error
    
    async def test_create_transaction_missing_fields(self, async_client: AsyncClient, test_user, test_db):
        """Test transaction creation with missing required fields."""
        user_id = test_user.id
        
        response = await async_client.post(
            f"/api/transactions?user_id={user_id}",
            json={
                "amount": "50.00",
                "description": "Missing date and type"
            }
        )
        
        assert response.status_code == 422
    
    async def test_list_transactions_empty(self, async_client: AsyncClient, test_user, test_db):
        """Test listing transactions when none exist."""
        user_id = test_user.id
        
        response = await async_client.get(f"/api/transactions?user_id={user_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["transactions"] == []
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["total_pages"] == 0
    
    async def test_list_transactions_with_data(self, async_client: AsyncClient, test_user, test_db, transaction_service):
        """Test listing transactions with data."""
        user_id = test_user.id
        
        # Create test transactions
        from app.schemas.transaction import TransactionCreate
        for i in range(5):
            transaction_data = TransactionCreate(
                amount=Decimal(f"{100 + i}.00"),
                date=datetime.now().date() - timedelta(days=i),
                description=f"Transaction {i}",
                type=TransactionType.EXPENSE,
                source=TransactionSource.MANUAL
            )
            await transaction_service.create_transaction(
                user_id=user_id,
                transaction_data=transaction_data
            )
        
        response = await async_client.get(f"/api/transactions?user_id={user_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["transactions"]) == 5
        assert data["total"] == 5
        assert data["page"] == 1
        assert data["total_pages"] == 1
    
    async def test_list_transactions_pagination(self, async_client: AsyncClient, test_user, test_db, transaction_service):
        """Test transaction list pagination."""
        user_id = test_user.id
        
        # Create 10 transactions
        for i in range(10):
            await create_test_transaction(
                transaction_service,
                user_id=user_id,
                amount=Decimal(f"{100 + i}.00"),
                date=(datetime.now() - timedelta(days=i)).date(),
                description=f"Transaction {i}",
                type=TransactionType.EXPENSE,
                source=TransactionSource.MANUAL
            )
        
        # Get first page
        response = await async_client.get(f"/api/transactions?user_id={user_id}&page=1&page_size=5")
        assert response.status_code == 200
        data = response.json()
        assert len(data["transactions"]) == 5
        assert data["total"] == 10
        assert data["page"] == 1
        assert data["total_pages"] == 2
        
        # Get second page
        response = await async_client.get(f"/api/transactions?user_id={user_id}&page=2&page_size=5")
        assert response.status_code == 200
        data = response.json()
        assert len(data["transactions"]) == 5
        assert data["page"] == 2
    
    async def test_list_transactions_filter_by_category(self, async_client: AsyncClient, test_user, test_db, transaction_service):
        """Test filtering transactions by category."""
        user_id = test_user.id
        
        # Create transactions with different categories
        await create_test_transaction(
            transaction_service,
            user_id=user_id,
            amount=Decimal("100.00"),
            date=datetime.now().date(),
            description="Groceries",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL,
            category="Groceries"
        )
        await create_test_transaction(
            transaction_service,
            user_id=user_id,
            amount=Decimal("50.00"),
            date=datetime.now().date(),
            description="Dining",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL,
            category="Dining"
        )
        
        response = await async_client.get(f"/api/transactions?user_id={user_id}&category=Groceries")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["transactions"]) == 1
        assert data["transactions"][0]["category"] == "Groceries"
    
    async def test_list_transactions_filter_by_type(self, async_client: AsyncClient, test_user, test_db, transaction_service):
        """Test filtering transactions by type."""
        user_id = test_user.id
        
        # Create income and expense transactions
        await create_test_transaction(
            transaction_service,
            user_id=user_id,
            amount=Decimal("1000.00"),
            date=datetime.now().date(),
            description="Salary",
            type=TransactionType.INCOME,
            source=TransactionSource.MANUAL
        )
        await create_test_transaction(
            transaction_service,
            user_id=user_id,
            amount=Decimal("50.00"),
            date=datetime.now().date(),
            description="Coffee",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL
        )
        
        response = await async_client.get(f"/api/transactions?user_id={user_id}&type=INCOME")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["transactions"]) == 1
        assert data["transactions"][0]["type"] == "INCOME"
    
    async def test_list_transactions_filter_by_date_range(self, async_client: AsyncClient, test_user, test_db, transaction_service):
        """Test filtering transactions by date range."""
        user_id = test_user.id
        
        # Create transactions on different dates
        await create_test_transaction(
            transaction_service,
            user_id=user_id,
            amount=Decimal("100.00"),
            date=datetime(2024, 1, 1).date(),
            description="Old transaction",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL
        )
        await create_test_transaction(
            transaction_service,
            user_id=user_id,
            amount=Decimal("50.00"),
            date=datetime(2024, 1, 15).date(),
            description="Recent transaction",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL
        )
        
        response = await async_client.get(
            f"/api/transactions?user_id={user_id}&start_date=2024-01-10T00:00:00&end_date=2024-01-20T00:00:00"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["transactions"]) == 1
        assert data["transactions"][0]["description"] == "Recent transaction"
    
    async def test_list_transactions_filter_by_amount_range(self, async_client: AsyncClient, test_user, test_db, transaction_service):
        """Test filtering transactions by amount range."""
        user_id = test_user.id
        
        # Create transactions with different amounts
        await create_test_transaction(
            transaction_service,
            user_id=user_id,
            amount=Decimal("10.00"),
            date=datetime.now().date(),
            description="Small",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL
        )
        await create_test_transaction(
            transaction_service,
            user_id=user_id,
            amount=Decimal("100.00"),
            date=datetime.now().date(),
            description="Large",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL
        )
        
        response = await async_client.get(
            f"/api/transactions?user_id={user_id}&min_amount=50&max_amount=150"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["transactions"]) == 1
        assert data["transactions"][0]["description"] == "Large"
    
    async def test_list_transactions_search(self, async_client: AsyncClient, test_user, test_db, transaction_service):
        """Test searching transactions by description."""
        user_id = test_user.id
        
        # Create transactions
        await create_test_transaction(
            transaction_service,
            user_id=user_id,
            amount=Decimal("100.00"),
            date=datetime.now().date(),
            description="Whole Foods Market",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL
        )
        await create_test_transaction(
            transaction_service,
            user_id=user_id,
            amount=Decimal("50.00"),
            date=datetime.now().date(),
            description="Starbucks Coffee",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL
        )
        
        response = await async_client.get(f"/api/transactions?user_id={user_id}&search=Foods")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["transactions"]) == 1
        assert "Foods" in data["transactions"][0]["description"]
    
    async def test_get_transaction_success(self, async_client: AsyncClient, test_user, test_db, transaction_service):
        """Test getting a single transaction."""
        user_id = test_user.id
        
        # Create transaction
        transaction = await create_test_transaction(
            transaction_service,
            user_id=user_id,
            amount=Decimal("100.00"),
            date=datetime.now().date(),
            description="Test transaction",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL
        )
        
        response = await async_client.get(f"/api/transactions/{transaction.id}?user_id={user_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(transaction.id)
        assert data["description"] == "Test transaction"
    
    async def test_get_transaction_not_found(self, async_client: AsyncClient, test_user, test_db):
        """Test getting a non-existent transaction."""
        user_id = test_user.id
        fake_id = uuid4()
        
        response = await async_client.get(f"/api/transactions/{fake_id}?user_id={user_id}")
        
        assert response.status_code == 404
    
    async def test_update_transaction_success(self, async_client: AsyncClient, test_user, test_db, transaction_service):
        """Test updating a transaction."""
        user_id = test_user.id
        
        # Create transaction
        transaction = await create_test_transaction(
            transaction_service,
            user_id=user_id,
            amount=Decimal("100.00"),
            date=datetime.now().date(),
            description="Original description",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL
        )
        
        # Update transaction
        response = await async_client.put(
            f"/api/transactions/{transaction.id}?user_id={user_id}",
            json={
                "description": "Updated description",
                "amount": "150.00"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["description"] == "Updated description"
        assert data["amount"] == "150.00"
    
    async def test_update_transaction_partial(self, async_client: AsyncClient, test_user, test_db, transaction_service):
        """Test partial update of a transaction."""
        user_id = test_user.id
        
        # Create transaction
        transaction = await create_test_transaction(
            transaction_service,
            user_id=user_id,
            amount=Decimal("100.00"),
            date=datetime.now().date(),
            description="Original",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL
        )
        
        # Update only description
        response = await async_client.put(
            f"/api/transactions/{transaction.id}?user_id={user_id}",
            json={"description": "Updated"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["description"] == "Updated"
        assert data["amount"] == "100.00"  # Unchanged
    
    async def test_update_transaction_not_found(self, async_client: AsyncClient, test_user, test_db):
        """Test updating a non-existent transaction."""
        user_id = test_user.id
        fake_id = uuid4()
        
        response = await async_client.put(
            f"/api/transactions/{fake_id}?user_id={user_id}",
            json={"description": "Updated"}
        )
        
        assert response.status_code == 404
    
    async def test_update_transaction_no_updates(self, async_client: AsyncClient, test_user, test_db, transaction_service):
        """Test updating a transaction with no changes."""
        user_id = test_user.id
        
        # Create transaction
        transaction = await create_test_transaction(
            transaction_service,
            user_id=user_id,
            amount=Decimal("100.00"),
            date=datetime.now().date(),
            description="Test",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL
        )
        
        # Update with empty dict
        response = await async_client.put(
            f"/api/transactions/{transaction.id}?user_id={user_id}",
            json={}
        )
        
        assert response.status_code == 400
    
    async def test_delete_transaction_success(self, async_client: AsyncClient, test_user, test_db, transaction_service):
        """Test deleting a transaction."""
        user_id = test_user.id
        
        # Create transaction
        transaction = await create_test_transaction(
            transaction_service,
            user_id=user_id,
            amount=Decimal("100.00"),
            date=datetime.now().date(),
            description="To be deleted",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL
        )
        
        # Delete transaction
        response = await async_client.delete(f"/api/transactions/{transaction.id}?user_id={user_id}")
        
        assert response.status_code == 204
        
        # Verify deletion
        get_response = await async_client.get(f"/api/transactions/{transaction.id}?user_id={user_id}")
        assert get_response.status_code == 404
    
    async def test_delete_transaction_not_found(self, async_client: AsyncClient, test_user, test_db):
        """Test deleting a non-existent transaction."""
        user_id = test_user.id
        fake_id = uuid4()
        
        response = await async_client.delete(f"/api/transactions/{fake_id}?user_id={user_id}")
        
        assert response.status_code == 404
