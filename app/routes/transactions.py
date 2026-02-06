"""Transaction API endpoints."""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user_id
from app.schemas.transaction import (
    TransactionCreate,
    TransactionUpdate as SchemaTransactionUpdate,
    TransactionResponse as SchemaTransactionResponse,
    TransactionSource,
    TransactionType,
)
from app.services.transaction_service import TransactionService

logger = logging.getLogger(__name__)
router = APIRouter()


# Response Models for API
class TransactionListResponse(BaseModel):
    """Transaction list response with pagination."""

    items: list[
        SchemaTransactionResponse
    ]  # Changed from 'transactions' to 'items' to match frontend
    total: int
    page: int
    page_size: int
    total_pages: int


# Dependency to get transaction service
async def get_transaction_service(db: AsyncSession = Depends(get_db)) -> TransactionService:
    """Get transaction service instance."""
    return TransactionService(db)


# Endpoints
@router.post("", response_model=SchemaTransactionResponse, status_code=201)
async def create_transaction(
    transaction: TransactionCreate,
    user_id: UUID = Depends(get_current_user_id),
    service: TransactionService = Depends(get_transaction_service),
) -> SchemaTransactionResponse:
    """Create a new transaction.

    Args:
        transaction: Transaction data
        user_id: User ID
        service: Transaction service

    Returns:
        Created transaction

    Raises:
        HTTPException: If creation fails
    """
    try:
        # Set source to MANUAL for API-created transactions
        transaction.source = TransactionSource.MANUAL

        created = await service.create_transaction(
            user_id=user_id, transaction_data=transaction, category=transaction.category
        )
        return SchemaTransactionResponse.model_validate(created)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create transaction: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred. Please try again later.")


@router.get("", response_model=TransactionListResponse)
async def list_transactions(
    user_id: UUID = Depends(get_current_user_id),
    category: Optional[str] = Query(None, description="Filter by category"),
    type: Optional[TransactionType] = Query(None, description="Filter by type"),
    start_date: Optional[datetime] = Query(None, description="Filter by start date"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date"),
    min_amount: Optional[Decimal] = Query(None, description="Filter by minimum amount"),
    max_amount: Optional[Decimal] = Query(None, description="Filter by maximum amount"),
    search: Optional[str] = Query(None, description="Search in description"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Page size"),
    service: TransactionService = Depends(get_transaction_service),
) -> TransactionListResponse:
    """List transactions with optional filters and pagination.

    Args:
        user_id: User ID
        category: Optional category filter
        type: Optional type filter
        start_date: Optional start date filter
        end_date: Optional end date filter
        min_amount: Optional minimum amount filter
        max_amount: Optional maximum amount filter
        search: Optional search term
        page: Page number
        page_size: Page size
        service: Transaction service

    Returns:
        Paginated list of transactions
    """
    try:
        from app.schemas.transaction import TransactionFilters, Pagination

        # Build filters
        filters = TransactionFilters(
            category=category,
            type=type,
            start_date=start_date.date() if start_date else None,
            end_date=end_date.date() if end_date else None,
            min_amount=min_amount,
            max_amount=max_amount,
            search=search,
        )

        # Build pagination
        pagination = Pagination(page=page, page_size=page_size)

        transactions, total = await service.list_transactions(
            user_id=user_id, filters=filters, pagination=pagination
        )

        total_pages = (total + page_size - 1) // page_size

        return TransactionListResponse(
            items=[SchemaTransactionResponse.model_validate(t) for t in transactions],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
    except Exception as e:
        logger.error(f"Failed to list transactions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred. Please try again later.")


@router.get("/{transaction_id}", response_model=SchemaTransactionResponse)
async def get_transaction(
    transaction_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    service: TransactionService = Depends(get_transaction_service),
) -> SchemaTransactionResponse:
    """Get a single transaction by ID.

    Args:
        transaction_id: Transaction ID
        user_id: User ID
        service: Transaction service

    Returns:
        Transaction details

    Raises:
        HTTPException: If transaction not found
    """
    try:
        transaction = await service.get_transaction(transaction_id, user_id)
        if not transaction:
            raise HTTPException(status_code=404, detail=f"Transaction {transaction_id} not found")
        return SchemaTransactionResponse.model_validate(transaction)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get transaction: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred. Please try again later.")


@router.put("/{transaction_id}", response_model=SchemaTransactionResponse)
async def update_transaction(
    transaction_id: UUID,
    updates: SchemaTransactionUpdate,
    user_id: UUID = Depends(get_current_user_id),
    service: TransactionService = Depends(get_transaction_service),
) -> SchemaTransactionResponse:
    """Update a transaction.

    Args:
        transaction_id: Transaction ID
        updates: Transaction updates
        user_id: User ID
        service: Transaction service

    Returns:
        Updated transaction

    Raises:
        HTTPException: If transaction not found or update fails
    """
    try:
        # Check if any updates provided
        update_dict = updates.model_dump(exclude_unset=True)

        if not update_dict:
            raise HTTPException(status_code=400, detail="No updates provided")

        # Pass the TransactionUpdate object directly to the service
        updated = await service.update_transaction(transaction_id, user_id, updates)
        if not updated:
            raise HTTPException(status_code=404, detail=f"Transaction {transaction_id} not found")

        return SchemaTransactionResponse.model_validate(updated)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update transaction: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred. Please try again later.")


class DeleteAllResponse(BaseModel):
    """Response for delete all transactions."""
    message: str
    deleted_count: int


@router.delete("/all", response_model=DeleteAllResponse)
async def delete_all_transactions(
    user_id: UUID = Depends(get_current_user_id),
    service: TransactionService = Depends(get_transaction_service),
) -> DeleteAllResponse:
    """Delete all transactions for a user.

    Args:
        user_id: User ID
        service: Transaction service

    Returns:
        Message with count of deleted transactions

    Raises:
        HTTPException: If deletion fails
    """
    try:
        # Delete all transactions efficiently
        deleted_count = await service.delete_all_transactions(user_id)
        
        logger.info(f"Deleted {deleted_count} transactions for user {user_id}")
        return DeleteAllResponse(
            message=f"Successfully deleted {deleted_count} transactions",
            deleted_count=deleted_count
        )
    except Exception as e:
        logger.error(f"Failed to delete all transactions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred. Please try again later.")


@router.delete("/{transaction_id}", status_code=204)
async def delete_transaction(
    transaction_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    service: TransactionService = Depends(get_transaction_service),
) -> None:
    """Delete a transaction.

    Args:
        transaction_id: Transaction ID
        user_id: User ID
        service: Transaction service

    Raises:
        HTTPException: If transaction not found or deletion fails
    """
    try:
        success = await service.delete_transaction(transaction_id, user_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Transaction {transaction_id} not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete transaction: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred. Please try again later.")
