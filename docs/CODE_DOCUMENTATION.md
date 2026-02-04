# Code Documentation Guide

## Overview

This document provides an overview of the codebase structure, key components, and coding conventions used in the AI Finance Platform.

## Table of Contents

1. [Project Structure](#project-structure)
2. [Core Components](#core-components)
3. [Database Layer](#database-layer)
4. [Service Layer](#service-layer)
5. [API Layer](#api-layer)
6. [ML Components](#ml-components)
7. [Testing](#testing)
8. [Coding Conventions](#coding-conventions)

---

## Project Structure

```
ai-finance-platform/
├── app/                      # Main application code
│   ├── models/              # SQLAlchemy ORM models
│   ├── schemas/             # Pydantic schemas for validation
│   ├── services/            # Business logic layer
│   ├── routes/              # FastAPI route handlers
│   ├── ml/                  # Machine learning components
│   ├── config.py            # Configuration management
│   ├── database.py          # Database connection setup
│   ├── cache.py             # Redis cache manager
│   ├── logging_config.py    # Logging configuration
│   └── main.py              # FastAPI application entry point
├── tests/                   # Test suite
├── alembic/                 # Database migrations
├── docs/                    # Documentation
├── frontend/                # React frontend application
├── models/                  # Trained ML models storage
├── scripts/                 # Utility scripts
├── docker-compose.yml       # Docker services configuration
├── Dockerfile.dev           # Development container
├── pyproject.toml           # Python dependencies
└── README.md                # Project overview
```

---

## Core Components

### Configuration (`app/config.py`)

Manages application configuration using Pydantic settings:

```python
class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    app_name: str = "AI Finance Platform"
    app_version: str = "1.0.0"
    debug: bool = False
    
    # Database
    database_url: str
    database_pool_size: int = 10
    
    # Redis
    redis_url: str
    
    # Security
    secret_key: str
    encryption_key: str
    
    class Config:
        env_file = ".env"
```

**Usage**:
```python
from app.config import settings

database_url = settings.database_url
```

### Database (`app/database.py`)

Manages database connections using SQLAlchemy async:

```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database session."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

**Usage in Routes**:
```python
@router.get("/transactions")
async def list_transactions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Use db session
    pass
```

### Cache (`app/cache.py`)

Redis cache manager for frequently accessed data:

```python
class CacheManager:
    """Redis cache manager."""
    
    async def get(self, key: str) -> Optional[str]:
        """Get value from cache."""
        
    async def set(self, key: str, value: str, expire: int = 3600):
        """Set value in cache with expiration."""
        
    async def delete(self, key: str):
        """Delete key from cache."""
```

**Usage**:
```python
from app.cache import cache_manager

# Get from cache
cached_data = await cache_manager.get(f"user:{user_id}:transactions")

# Set in cache (expires in 1 hour)
await cache_manager.set(f"user:{user_id}:transactions", json.dumps(data), expire=3600)
```

### Logging (`app/logging_config.py`)

Structured logging configuration:

```python
logger = get_logger(__name__)

logger.info("Transaction created", 
    user_id=user_id,
    transaction_id=transaction_id,
    amount=amount
)
```

---

## Database Layer

### Models (`app/models/`)

SQLAlchemy ORM models define database schema:

#### User Model (`app/models/user.py`)

```python
class User(Base):
    """User account model."""
    
    __tablename__ = "users"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[Optional[str]] = mapped_column(String(100))
    last_name: Mapped[Optional[str]] = mapped_column(String(100))
    
    # Relationships
    transactions: Mapped[List["Transaction"]] = relationship(back_populates="user")
    budgets: Mapped[List["Budget"]] = relationship(back_populates="user")
    goals: Mapped[List["FinancialGoal"]] = relationship(back_populates="user")
```

#### Transaction Model (`app/models/transaction.py`)

```python
class Transaction(Base):
    """Financial transaction model."""
    
    __tablename__ = "transactions"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    type: Mapped[TransactionType] = mapped_column(Enum(TransactionType), nullable=False)
    
    # Relationship
    user: Mapped["User"] = relationship(back_populates="transactions")
```

### Schemas (`app/schemas/`)

Pydantic schemas for request/response validation:

```python
class TransactionCreate(BaseModel):
    """Schema for creating a transaction."""
    
    amount: Decimal = Field(gt=0, description="Transaction amount")
    date: datetime.date = Field(description="Transaction date")
    description: str = Field(min_length=1, max_length=500)
    type: TransactionType
    category: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "amount": 125.50,
                "date": "2026-01-30",
                "description": "Whole Foods Market",
                "type": "EXPENSE"
            }
        }
```

---

## Service Layer

Services contain business logic and coordinate between models and routes.

### Transaction Service (`app/services/transaction_service.py`)

```python
class TransactionService:
    """Service for managing transactions."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_transaction(
        self,
        user_id: uuid.UUID,
        transaction_data: TransactionCreate
    ) -> Transaction:
        """
        Create a new transaction.
        
        Args:
            user_id: User ID
            transaction_data: Transaction data
            
        Returns:
            Created transaction
            
        Raises:
            DuplicateTransactionError: If duplicate detected
        """
        # Check for duplicates
        duplicate = await self._check_duplicate(user_id, transaction_data)
        if duplicate:
            raise DuplicateTransactionError("Similar transaction already exists")
        
        # Auto-categorize if needed
        if not transaction_data.category:
            transaction_data.category = await self._categorize(transaction_data.description)
        
        # Create transaction
        transaction = Transaction(
            user_id=user_id,
            **transaction_data.dict()
        )
        self.db.add(transaction)
        await self.db.flush()
        
        return transaction
```

### Budget Service (`app/services/budget_service.py`)

```python
class BudgetService:
    """Service for managing budgets."""
    
    async def get_budget_progress(
        self,
        budget_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> BudgetProgress:
        """
        Get budget progress with spending vs allocated amounts.
        
        Args:
            budget_id: Budget ID
            user_id: User ID
            
        Returns:
            Budget progress data
        """
        # Get budget
        budget = await self._get_budget(budget_id, user_id)
        
        # Get actual spending
        spending = await self._get_spending(budget, user_id)
        
        # Calculate progress
        progress = self._calculate_progress(budget, spending)
        
        # Generate alerts
        alerts = self._generate_alerts(progress)
        
        return BudgetProgress(
            budget_id=budget_id,
            progress=progress,
            alerts=alerts
        )
```

---

## API Layer

### Routes (`app/routes/`)

FastAPI route handlers define API endpoints:

```python
@router.post("/transactions", response_model=TransactionResponse, status_code=201)
async def create_transaction(
    transaction_data: TransactionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new transaction.
    
    Args:
        transaction_data: Transaction data
        db: Database session
        current_user: Authenticated user
        
    Returns:
        Created transaction
        
    Raises:
        HTTPException: If validation fails or duplicate detected
    """
    try:
        service = TransactionService(db)
        transaction = await service.create_transaction(
            user_id=current_user.id,
            transaction_data=transaction_data
        )
        return transaction
    except DuplicateTransactionError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error("Failed to create transaction", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
```

### Authentication (`app/routes/auth.py`)

JWT-based authentication:

```python
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Get current authenticated user from JWT token.
    
    Args:
        token: JWT access token
        db: Database session
        
    Returns:
        Authenticated user
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = await db.get(User, uuid.UUID(user_id))
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user
```

---

## ML Components

### Categorization Engine (`app/ml/categorization_engine.py`)

Automatic transaction categorization using NLP:

```python
class CategorizationEngine:
    """Engine for automatic transaction categorization."""
    
    def __init__(self):
        self.global_model = self._load_global_model()
        self.user_models = {}
    
    async def categorize(
        self,
        description: str,
        user_id: Optional[uuid.UUID] = None
    ) -> CategoryPrediction:
        """
        Categorize a transaction description.
        
        Args:
            description: Transaction description
            user_id: Optional user ID for personalized model
            
        Returns:
            Category prediction with confidence score
        """
        # Use user-specific model if available
        if user_id and self._has_user_model(user_id):
            model = self._get_user_model(user_id)
        else:
            model = self.global_model
        
        # Preprocess text
        processed = self._preprocess(description)
        
        # Predict category
        category = model.predict([processed])[0]
        confidence = model.predict_proba([processed]).max()
        
        return CategoryPrediction(
            category=category,
            confidence=confidence,
            model_type="user" if user_id else "global"
        )
```

### Prediction Engine (`app/ml/prediction_engine.py`)

Time series forecasting using ARIMA:

```python
class PredictionEngine:
    """Engine for expense prediction using ARIMA."""
    
    async def forecast_expenses(
        self,
        user_id: uuid.UUID,
        category: str,
        periods: int = 30
    ) -> ForecastResult:
        """
        Forecast expenses for a category.
        
        Args:
            user_id: User ID
            category: Expense category
            periods: Number of days to forecast
            
        Returns:
            Forecast with confidence intervals
        """
        # Get historical data
        history = await self._get_historical_data(user_id, category)
        
        # Check if sufficient data
        if len(history) < 90:
            raise InsufficientDataError("Need at least 90 days of history")
        
        # Fit ARIMA model
        model = self._fit_arima(history)
        
        # Generate forecast
        forecast = model.forecast(steps=periods)
        confidence_interval = model.get_forecast(steps=periods).conf_int()
        
        return ForecastResult(
            category=category,
            periods=periods,
            predictions=forecast.tolist(),
            confidence_interval=confidence_interval.tolist()
        )
```

---

## Testing

### Test Structure

```
tests/
├── conftest.py              # Pytest fixtures
├── test_models.py           # Model tests
├── test_transaction_service.py
├── test_budget_service.py
├── test_categorization_engine.py
├── test_prediction_engine.py
├── test_transaction_routes.py
└── test_e2e_integration.py
```

### Writing Tests

#### Unit Tests

```python
@pytest.mark.asyncio
async def test_create_transaction(db_session, test_user):
    """Test creating a transaction."""
    service = TransactionService(db_session)
    
    transaction_data = TransactionCreate(
        amount=Decimal("125.50"),
        date=datetime.date.today(),
        description="Test transaction",
        type=TransactionType.EXPENSE,
        category="Groceries"
    )
    
    transaction = await service.create_transaction(
        user_id=test_user.id,
        transaction_data=transaction_data
    )
    
    assert transaction.id is not None
    assert transaction.amount == Decimal("125.50")
    assert transaction.category == "Groceries"
```

#### Property-Based Tests

```python
from hypothesis import given, strategies as st

@given(
    amount=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("1000000"), places=2),
    description=st.text(min_size=1, max_size=200)
)
@pytest.mark.asyncio
async def test_transaction_persistence_round_trip(db_session, test_user, amount, description):
    """Property test: Creating and retrieving a transaction should preserve all fields."""
    service = TransactionService(db_session)
    
    # Create transaction
    transaction_data = TransactionCreate(
        amount=amount,
        date=datetime.date.today(),
        description=description,
        type=TransactionType.EXPENSE
    )
    
    created = await service.create_transaction(test_user.id, transaction_data)
    
    # Retrieve transaction
    retrieved = await service.get_transaction(created.id, test_user.id)
    
    # Verify all fields match
    assert retrieved.amount == amount
    assert retrieved.description == description
```

---

## Coding Conventions

### Python Style Guide

Follow PEP 8 and use these tools:

- **Formatter**: Black (line length: 100)
- **Linter**: Ruff
- **Type Checker**: MyPy

### Naming Conventions

- **Classes**: PascalCase (`TransactionService`, `User`)
- **Functions/Methods**: snake_case (`create_transaction`, `get_budget_progress`)
- **Constants**: UPPER_SNAKE_CASE (`MAX_TRANSACTIONS`, `DEFAULT_LIMIT`)
- **Private Methods**: Leading underscore (`_check_duplicate`, `_calculate_progress`)

### Docstrings

Use Google-style docstrings:

```python
def calculate_savings_rate(income: Decimal, expenses: Decimal) -> float:
    """
    Calculate savings rate as a percentage.
    
    Args:
        income: Total income
        expenses: Total expenses
        
    Returns:
        Savings rate as percentage (0-100)
        
    Raises:
        ValueError: If income is zero or negative
        
    Example:
        >>> calculate_savings_rate(Decimal("5000"), Decimal("3000"))
        40.0
    """
    if income <= 0:
        raise ValueError("Income must be positive")
    
    return float((income - expenses) / income * 100)
```

### Type Hints

Always use type hints:

```python
from typing import Optional, List
from decimal import Decimal

async def get_transactions(
    user_id: uuid.UUID,
    category: Optional[str] = None,
    limit: int = 50
) -> List[Transaction]:
    """Get transactions with optional filtering."""
    pass
```

### Error Handling

Use custom exceptions:

```python
class DuplicateTransactionError(Exception):
    """Raised when a duplicate transaction is detected."""
    pass

class InsufficientDataError(Exception):
    """Raised when insufficient data for ML operations."""
    pass
```

### Async/Await

Use async/await for I/O operations:

```python
# Good
async def get_user(user_id: uuid.UUID) -> User:
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

# Bad - blocking I/O
def get_user(user_id: uuid.UUID) -> User:
    session = Session()
    return session.query(User).filter(User.id == user_id).first()
```

---

## Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Pytest Documentation](https://docs.pytest.org/)
- [Hypothesis Documentation](https://hypothesis.readthedocs.io/)

---

**Version**: 1.0.0  
**Last Updated**: January 30, 2026
