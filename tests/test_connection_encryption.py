"""Tests for Connection model encryption."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.connection import Connection
from app.models.user import User


class TestConnectionEncryption:
    """Test suite for Connection model encryption."""

    async def test_access_token_encrypted_at_rest(self, db_session: AsyncSession, test_user: User):
        """Test that access_token is encrypted when stored in database."""
        plaintext_token = "plaid-access-token-12345"
        
        # Create connection with plaintext token
        connection = Connection(
            user_id=test_user.id,
            institution_id="ins_123",
            institution_name="Test Bank",
            status="ACTIVE"
        )
        connection.access_token = plaintext_token
        
        db_session.add(connection)
        await db_session.commit()
        
        # Verify encrypted value is different from plaintext
        assert connection._access_token_encrypted != plaintext_token
        # Verify we can still read the plaintext via property
        assert connection.access_token == plaintext_token

    async def test_access_token_decryption_on_read(self, db_session: AsyncSession, test_user: User):
        """Test that access_token is decrypted when read from database."""
        plaintext_token = "plaid-access-token-67890"
        
        # Create and save connection
        connection = Connection(
            user_id=test_user.id,
            institution_id="ins_456",
            institution_name="Another Bank",
            status="ACTIVE"
        )
        connection.access_token = plaintext_token
        
        db_session.add(connection)
        await db_session.commit()
        connection_id = connection.id
        
        # Clear session to force reload from database
        db_session.expire_all()
        
        # Reload connection from database
        result = await db_session.execute(
            select(Connection).filter_by(id=connection_id)
        )
        reloaded_connection = result.scalar_one()
        
        # Verify decrypted token matches original
        assert reloaded_connection.access_token == plaintext_token

    async def test_access_token_update(self, db_session: AsyncSession, test_user: User):
        """Test that updating access_token re-encrypts the value."""
        original_token = "original-token-123"
        new_token = "new-token-456"
        
        # Create connection
        connection = Connection(
            user_id=test_user.id,
            institution_id="ins_789",
            institution_name="Update Bank",
            status="ACTIVE"
        )
        connection.access_token = original_token
        
        db_session.add(connection)
        await db_session.commit()
        
        original_encrypted = connection._access_token_encrypted
        
        # Update token
        connection.access_token = new_token
        await db_session.commit()
        
        # Verify encrypted value changed
        assert connection._access_token_encrypted != original_encrypted
        # Verify new plaintext is correct
        assert connection.access_token == new_token

    async def test_multiple_connections_different_encryption(self, db_session: AsyncSession, test_user: User):
        """Test that same token encrypts differently for different connections."""
        same_token = "shared-token-123"
        
        # Create two connections with same token
        connection1 = Connection(
            user_id=test_user.id,
            institution_id="ins_111",
            institution_name="Bank 1",
            status="ACTIVE"
        )
        connection1.access_token = same_token
        
        connection2 = Connection(
            user_id=test_user.id,
            institution_id="ins_222",
            institution_name="Bank 2",
            status="ACTIVE"
        )
        connection2.access_token = same_token
        
        db_session.add_all([connection1, connection2])
        await db_session.commit()
        
        # Encrypted values should differ (due to IV/timestamp in Fernet)
        assert connection1._access_token_encrypted != connection2._access_token_encrypted
        # But both decrypt to same value
        assert connection1.access_token == same_token
        assert connection2.access_token == same_token

    async def test_connection_with_special_characters_in_token(self, db_session: AsyncSession, test_user: User):
        """Test encryption of tokens with special characters."""
        special_token = "token!@#$%^&*()_+-=[]{}|;':\",./<>?"
        
        connection = Connection(
            user_id=test_user.id,
            institution_id="ins_special",
            institution_name="Special Bank",
            status="ACTIVE"
        )
        connection.access_token = special_token
        
        db_session.add(connection)
        await db_session.commit()
        connection_id = connection.id
        db_session.expire_all()
        
        result = await db_session.execute(
            select(Connection).filter_by(id=connection_id)
        )
        reloaded = result.scalar_one()
        assert reloaded.access_token == special_token

    async def test_connection_with_long_token(self, db_session: AsyncSession, test_user: User):
        """Test encryption of very long tokens."""
        long_token = "a" * 5000  # 5KB token
        
        connection = Connection(
            user_id=test_user.id,
            institution_id="ins_long",
            institution_name="Long Token Bank",
            status="ACTIVE"
        )
        connection.access_token = long_token
        
        db_session.add(connection)
        await db_session.commit()
        connection_id = connection.id
        db_session.expire_all()
        
        result = await db_session.execute(
            select(Connection).filter_by(id=connection_id)
        )
        reloaded = result.scalar_one()
        assert reloaded.access_token == long_token
        assert len(reloaded.access_token) == 5000
