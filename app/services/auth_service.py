"""Authentication service for user registration, login, and token management."""

import re
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

import bcrypt
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)


class PasswordValidationError(Exception):
    """Exception raised when password doesn't meet requirements."""

    pass


class AuthenticationError(Exception):
    """Exception raised when authentication fails."""

    pass


class TokenError(Exception):
    """Exception raised when token operations fail."""

    pass


class AuthService:
    """Service for handling authentication operations."""

    # Password requirements
    MIN_PASSWORD_LENGTH = 12

    def __init__(self, db: AsyncSession):
        """Initialize authentication service.

        Args:
            db: Database session
        """
        self.db = db

    def validate_password(self, password: str) -> None:
        """Validate password meets security requirements.

        Requirement 8.1: Enforce strong password requirements
        - Minimum 12 characters
        - Mixed case (uppercase and lowercase)
        - Numbers
        - Special characters

        Args:
            password: Password to validate

        Raises:
            PasswordValidationError: If password doesn't meet requirements
        """
        if len(password) < self.MIN_PASSWORD_LENGTH:
            raise PasswordValidationError(
                f"Password must be at least {self.MIN_PASSWORD_LENGTH} characters long"
            )

        if not re.search(r"[a-z]", password):
            raise PasswordValidationError("Password must contain at least one lowercase letter")

        if not re.search(r"[A-Z]", password):
            raise PasswordValidationError("Password must contain at least one uppercase letter")

        if not re.search(r"\d", password):
            raise PasswordValidationError("Password must contain at least one number")

        if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?~`]", password):
            raise PasswordValidationError(
                "Password must contain at least one special character"
            )

    def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt.

        Args:
            password: Plain text password

        Returns:
            Hashed password
        """
        # Convert password to bytes and hash
        password_bytes = password.encode("utf-8")
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode("utf-8")

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash.

        Args:
            plain_password: Plain text password
            hashed_password: Hashed password to verify against

        Returns:
            True if password matches, False otherwise
        """
        password_bytes = plain_password.encode("utf-8")
        hashed_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(password_bytes, hashed_bytes)

    async def register_user(
        self,
        email: str,
        password: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ) -> User:
        """Register a new user.

        Requirement 8.1: User registration with password hashing

        Args:
            email: User email address
            password: Plain text password
            first_name: User's first name (optional)
            last_name: User's last name (optional)

        Returns:
            Created user object

        Raises:
            PasswordValidationError: If password doesn't meet requirements
            ValueError: If email already exists
        """
        logger.info("Registering new user", email=email)

        # Validate password
        self.validate_password(password)

        # Check if email already exists
        stmt = select(User).where(User.email == email)
        result = await self.db.execute(stmt)
        existing_user = result.scalar_one_or_none()

        if existing_user:
            logger.warning("Registration failed: email already exists", email=email)
            raise ValueError(f"User with email {email} already exists")

        # Hash password
        password_hash = self.hash_password(password)

        # Create user
        user = User(
            email=email, password_hash=password_hash, first_name=first_name, last_name=last_name
        )

        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)

        logger.info("User registered successfully", user_id=str(user.id), email=email)

        return user

    async def authenticate_user(self, email: str, password: str) -> User:
        """Authenticate a user with email and password.

        Args:
            email: User email address
            password: Plain text password

        Returns:
            Authenticated user object

        Raises:
            AuthenticationError: If authentication fails
        """
        logger.info("Authenticating user", email=email)

        # Get user by email
        stmt = select(User).where(User.email == email)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            logger.warning("Authentication failed: user not found", email=email)
            raise AuthenticationError("Invalid email or password")

        # Verify password
        if not self.verify_password(password, user.password_hash):
            logger.warning("Authentication failed: invalid password", email=email)
            raise AuthenticationError("Invalid email or password")

        logger.info("User authenticated successfully", user_id=str(user.id), email=email)

        return user

    def create_access_token(self, user_id: UUID, expires_delta: Optional[timedelta] = None) -> str:
        """Create a JWT access token.

        Requirement 8.1: JWT token generation

        Args:
            user_id: User ID to encode in token
            expires_delta: Token expiration time (default: 30 minutes)

        Returns:
            JWT access token
        """
        if expires_delta is None:
            expires_delta = timedelta(minutes=30)

        expire = datetime.now(timezone.utc) + expires_delta

        to_encode = {"sub": str(user_id), "exp": expire, "type": "access"}

        encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm="HS256")

        logger.debug("Access token created", user_id=str(user_id))

        return encoded_jwt

    def create_refresh_token(self, user_id: UUID, expires_delta: Optional[timedelta] = None) -> str:
        """Create a JWT refresh token.

        Requirement 8.1: Token refresh mechanism

        Args:
            user_id: User ID to encode in token
            expires_delta: Token expiration time (default: 7 days)

        Returns:
            JWT refresh token
        """
        if expires_delta is None:
            expires_delta = timedelta(days=7)

        expire = datetime.now(timezone.utc) + expires_delta

        to_encode = {"sub": str(user_id), "exp": expire, "type": "refresh"}

        encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm="HS256")

        logger.debug("Refresh token created", user_id=str(user_id))

        return encoded_jwt

    def verify_token(self, token: str, token_type: str = "access") -> UUID:
        """Verify and decode a JWT token.

        Args:
            token: JWT token to verify
            token_type: Expected token type ("access" or "refresh")

        Returns:
            User ID from token

        Raises:
            TokenError: If token is invalid or expired
        """
        try:
            payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])

            user_id_str: str = payload.get("sub")
            token_type_in_token: str = payload.get("type")

            if user_id_str is None:
                raise TokenError("Token missing user ID")

            if token_type_in_token != token_type:
                raise TokenError(
                    f"Invalid token type: expected {token_type}, got {token_type_in_token}"
                )

            user_id = UUID(user_id_str)

            logger.debug("Token verified successfully", user_id=str(user_id))

            return user_id

        except JWTError as e:
            logger.warning("Token verification failed", error=str(e))
            raise TokenError(f"Invalid token: {str(e)}")

    async def refresh_access_token(self, refresh_token: str) -> tuple[str, str]:
        """Refresh access token using refresh token.

        Requirement 8.1: Token refresh mechanism

        Args:
            refresh_token: Valid refresh token

        Returns:
            Tuple of (new_access_token, new_refresh_token)

        Raises:
            TokenError: If refresh token is invalid
        """
        # Verify refresh token
        user_id = self.verify_token(refresh_token, token_type="refresh")

        # Verify user still exists
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            logger.warning("Token refresh failed: user not found", user_id=str(user_id))
            raise TokenError("User not found")

        # Create new tokens
        new_access_token = self.create_access_token(user_id)
        new_refresh_token = self.create_refresh_token(user_id)

        logger.info("Tokens refreshed successfully", user_id=str(user_id))

        return new_access_token, new_refresh_token

    async def get_current_user(self, token: str) -> User:
        """Get current user from access token.

        Args:
            token: JWT access token

        Returns:
            User object

        Raises:
            TokenError: If token is invalid
            AuthenticationError: If user not found
        """
        # Verify token
        user_id = self.verify_token(token, token_type="access")

        # Get user
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            logger.warning("Get current user failed: user not found", user_id=str(user_id))
            raise AuthenticationError("User not found")

        return user

    async def change_password(
        self, user_id: UUID, current_password: str, new_password: str
    ) -> None:
        """Change user password.

        Args:
            user_id: User ID
            current_password: Current password for verification
            new_password: New password to set

        Raises:
            AuthenticationError: If current password is incorrect
            PasswordValidationError: If new password doesn't meet requirements
        """
        logger.info("Changing password", user_id=str(user_id))

        # Get user
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            raise AuthenticationError("User not found")

        # Verify current password
        if not self.verify_password(current_password, user.password_hash):
            logger.warning(
                "Password change failed: incorrect current password", user_id=str(user_id)
            )
            raise AuthenticationError("Current password is incorrect")

        # Validate new password
        self.validate_password(new_password)

        # Hash and update password
        user.password_hash = self.hash_password(new_password)
        user.updated_at = datetime.now(timezone.utc)

        await self.db.flush()

        logger.info("Password changed successfully", user_id=str(user_id))

    async def blacklist_token(self, token: str, expires_in: int = None) -> None:
        """Add a token to the blacklist. Token will be auto-removed from Redis when it naturally expires."""
        from app.cache import cache_manager

        if expires_in is None:
            try:
                payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
                exp = payload.get("exp", 0)
                expires_in = max(0, exp - int(datetime.now(timezone.utc).timestamp()))
            except JWTError:
                expires_in = 30 * 60  # Default 30 minutes
        
        await cache_manager.set(f"blacklist:{token}", "1", expire=expires_in)

    async def is_token_blacklisted(self, token: str) -> bool:
        """Check if a token has been blacklisted."""
        from app.cache import cache_manager

        result = await cache_manager.get(f"blacklist:{token}")
        return result is not None
