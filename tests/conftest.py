"""Pytest configuration and fixtures."""

import asyncio
import os
from typing import AsyncGenerator, Generator

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.database import Base, get_db
from app.main import app

# Test database URL - use environment variable or default to localhost
# In Docker, this will be set to use the 'postgres' service name
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_finance_platform_test",
)

# Create test engine
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False, pool_pre_ping=True)

# Create test session factory
TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
def setup_test_database(event_loop):
    """Create database tables once for the entire test session."""

    async def _setup():
        # Create tables
        try:
            async with test_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        except Exception as e:
            print(f"WARNING: Database setup failed, skipping. Error: {e}")
            return False
        return True

    async def _teardown():
        # Drop tables after all tests complete
        try:
            async with test_engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
            await test_engine.dispose()
        except Exception:
            pass

    # Run setup
    success = event_loop.run_until_complete(_setup())

    yield

    # Run teardown if setup was successful
    if success:
        event_loop.run_until_complete(_teardown())


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test using savepoints."""
    # Create a connection
    connection = await test_engine.connect()

    # Begin a transaction
    transaction = await connection.begin()

    # Create a session bound to the connection with savepoint support
    session = AsyncSession(
        bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )

    yield session

    # Close session and rollback the transaction (undoes all changes made during the test)
    await session.close()
    await transaction.rollback()
    await connection.close()


@pytest.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create test client with database session override."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(app=app, base_url="http://test") as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
async def test_user(db_session: AsyncSession):
    """Create a test user."""
    from app.models.user import User
    from app.services.auth_service import AuthService

    # Use AuthService to properly hash the password
    auth_service = AuthService(db_session)
    password_hash = auth_service.hash_password("TestPassword123!@#")

    user = User(
        email="test@example.com", password_hash=password_hash, first_name="Test", last_name="User"
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def auth_headers(test_user):
    """Create authentication headers for test user."""
    from app.services.auth_service import AuthService

    auth_service = AuthService(None)  # No DB needed for token creation
    access_token = auth_service.create_access_token(test_user.id)
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create async test client with database session override."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(app=app, base_url="http://test") as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
async def test_db(db_session: AsyncSession) -> AsyncSession:
    """Alias for db_session for clearer test code."""
    return db_session


@pytest.fixture
async def transaction_service(db_session: AsyncSession):
    """Create transaction service instance."""
    from app.services.transaction_service import TransactionService

    return TransactionService(db_session)
