"""Tests for authentication service."""

import pytest
from datetime import timedelta
from uuid import uuid4

from app.services.auth_service import (
    AuthService,
    PasswordValidationError,
    AuthenticationError,
    TokenError,
)


class TestPasswordValidation:
    """Tests for password validation."""

    async def test_validate_password_success(self, db_session):
        """Test that valid passwords pass validation."""
        auth_service = AuthService(db_session)

        # Should not raise any exception
        auth_service.validate_password("ValidPass123!@#")
        auth_service.validate_password("AnotherGood1$Pass")
        auth_service.validate_password("Str0ng&Secure!")

    async def test_validate_password_too_short(self, db_session):
        """Test that passwords shorter than 12 characters are rejected."""
        auth_service = AuthService(db_session)

        with pytest.raises(PasswordValidationError) as exc_info:
            auth_service.validate_password("Short1!")

        assert "at least 12 characters" in str(exc_info.value)

    async def test_validate_password_missing_lowercase(self, db_session):
        """Test that passwords without lowercase letters are rejected."""
        auth_service = AuthService(db_session)

        with pytest.raises(PasswordValidationError) as exc_info:
            auth_service.validate_password("ALLUPPERCASE123!")

        assert "lowercase letter" in str(exc_info.value)

    async def test_validate_password_missing_uppercase(self, db_session):
        """Test that passwords without uppercase letters are rejected."""
        auth_service = AuthService(db_session)

        with pytest.raises(PasswordValidationError) as exc_info:
            auth_service.validate_password("alllowercase123!")

        assert "uppercase letter" in str(exc_info.value)

    async def test_validate_password_missing_number(self, db_session):
        """Test that passwords without numbers are rejected."""
        auth_service = AuthService(db_session)

        with pytest.raises(PasswordValidationError) as exc_info:
            auth_service.validate_password("NoNumbersHere!")

        assert "number" in str(exc_info.value)

    async def test_validate_password_missing_special_char(self, db_session):
        """Test that passwords without special characters are rejected."""
        auth_service = AuthService(db_session)

        with pytest.raises(PasswordValidationError) as exc_info:
            auth_service.validate_password("NoSpecialChar123")

        assert "special character" in str(exc_info.value)


class TestPasswordHashing:
    """Tests for password hashing and verification."""

    async def test_hash_and_verify_password(self, db_session):
        """Test that passwords can be hashed and verified."""
        auth_service = AuthService(db_session)

        password = "ValidPass123!@#"
        hashed = auth_service.hash_password(password)

        # Hash should be different from original
        assert hashed != password

        # Should verify correctly
        assert auth_service.verify_password(password, hashed) is True

        # Wrong password should not verify
        assert auth_service.verify_password("WrongPass123!", hashed) is False


class TestUserRegistration:
    """Tests for user registration."""

    async def test_register_user_success(self, db_session):
        """Test successful user registration."""
        auth_service = AuthService(db_session)

        user = await auth_service.register_user(
            email="newuser@example.com",
            password="ValidPass123!@#",
            first_name="John",
            last_name="Doe",
        )

        assert user.id is not None
        assert user.email == "newuser@example.com"
        assert user.first_name == "John"
        assert user.last_name == "Doe"
        assert user.password_hash != "ValidPass123!@#"
        assert user.created_at is not None

    async def test_register_user_duplicate_email(self, db_session, test_user):
        """Test that duplicate email addresses are rejected."""
        auth_service = AuthService(db_session)

        with pytest.raises(ValueError) as exc_info:
            await auth_service.register_user(email=test_user.email, password="ValidPass123!@#")

        assert "already exists" in str(exc_info.value)

    async def test_register_user_weak_password(self, db_session):
        """Test that weak passwords are rejected during registration."""
        auth_service = AuthService(db_session)

        with pytest.raises(PasswordValidationError):
            await auth_service.register_user(email="newuser@example.com", password="weak")


class TestUserAuthentication:
    """Tests for user authentication."""

    async def test_authenticate_user_success(self, db_session):
        """Test successful user authentication."""
        auth_service = AuthService(db_session)

        # Register a user first
        password = "ValidPass123!@#"
        registered_user = await auth_service.register_user(
            email="auth@example.com", password=password
        )

        # Authenticate
        authenticated_user = await auth_service.authenticate_user(
            email="auth@example.com", password=password
        )

        assert authenticated_user.id == registered_user.id
        assert authenticated_user.email == registered_user.email

    async def test_authenticate_user_invalid_email(self, db_session):
        """Test authentication with non-existent email."""
        auth_service = AuthService(db_session)

        with pytest.raises(AuthenticationError) as exc_info:
            await auth_service.authenticate_user(
                email="nonexistent@example.com", password="ValidPass123!@#"
            )

        assert "Invalid email or password" in str(exc_info.value)

    async def test_authenticate_user_invalid_password(self, db_session):
        """Test authentication with incorrect password."""
        auth_service = AuthService(db_session)

        # Register a user first
        await auth_service.register_user(email="auth@example.com", password="ValidPass123!@#")

        # Try to authenticate with wrong password
        with pytest.raises(AuthenticationError) as exc_info:
            await auth_service.authenticate_user(email="auth@example.com", password="WrongPass123!")

        assert "Invalid email or password" in str(exc_info.value)


class TestTokenOperations:
    """Tests for JWT token operations."""

    async def test_create_access_token(self, db_session, test_user):
        """Test access token creation."""
        auth_service = AuthService(db_session)

        token = auth_service.create_access_token(test_user.id)

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    async def test_create_refresh_token(self, db_session, test_user):
        """Test refresh token creation."""
        auth_service = AuthService(db_session)

        token = auth_service.create_refresh_token(test_user.id)

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    async def test_verify_token_success(self, db_session, test_user):
        """Test successful token verification."""
        auth_service = AuthService(db_session)

        # Create and verify access token
        access_token = auth_service.create_access_token(test_user.id)
        user_id = auth_service.verify_token(access_token, token_type="access")

        assert user_id == test_user.id

        # Create and verify refresh token
        refresh_token = auth_service.create_refresh_token(test_user.id)
        user_id = auth_service.verify_token(refresh_token, token_type="refresh")

        assert user_id == test_user.id

    async def test_verify_token_invalid(self, db_session):
        """Test verification of invalid token."""
        auth_service = AuthService(db_session)

        with pytest.raises(TokenError):
            auth_service.verify_token("invalid.token.here", token_type="access")

    async def test_verify_token_wrong_type(self, db_session, test_user):
        """Test verification with wrong token type."""
        auth_service = AuthService(db_session)

        # Create access token but verify as refresh token
        access_token = auth_service.create_access_token(test_user.id)

        with pytest.raises(TokenError) as exc_info:
            auth_service.verify_token(access_token, token_type="refresh")

        assert "Invalid token type" in str(exc_info.value)

    async def test_verify_token_expired(self, db_session, test_user):
        """Test verification of expired token."""
        auth_service = AuthService(db_session)

        # Create token with negative expiry (already expired)
        expired_token = auth_service.create_access_token(
            test_user.id, expires_delta=timedelta(seconds=-1)
        )

        with pytest.raises(TokenError):
            auth_service.verify_token(expired_token, token_type="access")


class TestTokenRefresh:
    """Tests for token refresh mechanism."""

    async def test_refresh_access_token(self, db_session, test_user):
        """Test refreshing access token with valid refresh token."""
        auth_service = AuthService(db_session)

        # Create refresh token
        refresh_token = auth_service.create_refresh_token(test_user.id)

        # Refresh tokens
        new_access_token, new_refresh_token = await auth_service.refresh_access_token(refresh_token)

        assert new_access_token is not None
        assert new_refresh_token is not None
        assert new_access_token != refresh_token
        # New refresh token should be different (generated at different time)
        assert isinstance(new_refresh_token, str)
        assert len(new_refresh_token) > 0

        # Verify new tokens work
        user_id = auth_service.verify_token(new_access_token, token_type="access")
        assert user_id == test_user.id

    async def test_refresh_access_token_invalid_token(self, db_session):
        """Test refresh with invalid token."""
        auth_service = AuthService(db_session)

        with pytest.raises(TokenError):
            await auth_service.refresh_access_token("invalid.token.here")

    async def test_refresh_access_token_user_not_found(self, db_session):
        """Test refresh when user no longer exists."""
        auth_service = AuthService(db_session)

        # Create token for non-existent user
        fake_user_id = uuid4()
        refresh_token = auth_service.create_refresh_token(fake_user_id)

        with pytest.raises(TokenError) as exc_info:
            await auth_service.refresh_access_token(refresh_token)

        assert "User not found" in str(exc_info.value)


class TestGetCurrentUser:
    """Tests for getting current user from token."""

    async def test_get_current_user_success(self, db_session, test_user):
        """Test getting current user with valid token."""
        auth_service = AuthService(db_session)

        # Create access token
        access_token = auth_service.create_access_token(test_user.id)

        # Get current user
        user = await auth_service.get_current_user(access_token)

        assert user.id == test_user.id
        assert user.email == test_user.email

    async def test_get_current_user_invalid_token(self, db_session):
        """Test getting current user with invalid token."""
        auth_service = AuthService(db_session)

        with pytest.raises(TokenError):
            await auth_service.get_current_user("invalid.token.here")

    async def test_get_current_user_not_found(self, db_session):
        """Test getting current user when user doesn't exist."""
        auth_service = AuthService(db_session)

        # Create token for non-existent user
        fake_user_id = uuid4()
        access_token = auth_service.create_access_token(fake_user_id)

        with pytest.raises(AuthenticationError) as exc_info:
            await auth_service.get_current_user(access_token)

        assert "User not found" in str(exc_info.value)


class TestChangePassword:
    """Tests for password change functionality."""

    async def test_change_password_success(self, db_session):
        """Test successful password change."""
        auth_service = AuthService(db_session)

        # Register user
        old_password = "OldPass123!@#"
        new_password = "NewPass456!@#"
        user = await auth_service.register_user(
            email="changepass@example.com", password=old_password
        )

        # Change password
        await auth_service.change_password(
            user_id=user.id, current_password=old_password, new_password=new_password
        )

        # Verify old password no longer works
        with pytest.raises(AuthenticationError):
            await auth_service.authenticate_user(
                email="changepass@example.com", password=old_password
            )

        # Verify new password works
        authenticated_user = await auth_service.authenticate_user(
            email="changepass@example.com", password=new_password
        )
        assert authenticated_user.id == user.id

    async def test_change_password_wrong_current(self, db_session):
        """Test password change with incorrect current password."""
        auth_service = AuthService(db_session)

        # Register user
        password = "OldPass123!@#"
        user = await auth_service.register_user(email="changepass@example.com", password=password)

        # Try to change with wrong current password
        with pytest.raises(AuthenticationError) as exc_info:
            await auth_service.change_password(
                user_id=user.id, current_password="WrongPass123!", new_password="NewPass456!@#"
            )

        assert "incorrect" in str(exc_info.value).lower()

    async def test_change_password_weak_new_password(self, db_session):
        """Test password change with weak new password."""
        auth_service = AuthService(db_session)

        # Register user
        password = "OldPass123!@#"
        user = await auth_service.register_user(email="changepass@example.com", password=password)

        # Try to change to weak password
        with pytest.raises(PasswordValidationError):
            await auth_service.change_password(
                user_id=user.id, current_password=password, new_password="weak"
            )
