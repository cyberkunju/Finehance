"""API routes for authentication."""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.database import get_db
from app.config import settings
from app.services.auth_service import (
    AuthService,
    PasswordValidationError,
    AuthenticationError,
    TokenError,
)
from app.schemas.auth import (
    UserRegisterRequest,
    UserLoginRequest,
    TokenRefreshRequest,
    AuthResponse,
    TokenResponse,
    UserResponse,
    MessageResponse,
)
from fastapi.security import OAuth2PasswordBearer
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# Rate limiter for auth endpoints (stricter limits)
limiter = Limiter(key_func=get_remote_address)


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(f"{settings.auth_rate_limit_per_minute}/minute")
async def register(
    request_data: UserRegisterRequest, request: Request, db: AsyncSession = Depends(get_db)
) -> AuthResponse:
    """Register a new user.

    Args:
        request_data: User registration request
        request: HTTP request (for rate limiting)
        db: Database session

    Returns:
        User information and authentication tokens

    Raises:
        HTTPException: If registration fails
    """
    logger.info("User registration request", email=request_data.email)

    auth_service = AuthService(db)

    try:
        # Register user
        user = await auth_service.register_user(
            email=request_data.email,
            password=request_data.password,
            first_name=request_data.first_name,
            last_name=request_data.last_name,
        )

        # Generate tokens
        access_token = auth_service.create_access_token(user.id)
        refresh_token = auth_service.create_refresh_token(user.id)

        logger.info("User registered successfully", user_id=str(user.id), email=user.email)

        return AuthResponse(
            user=UserResponse(
                id=user.id,
                email=user.email,
                first_name=user.first_name,
                last_name=user.last_name,
                created_at=user.created_at,
            ),
            tokens=TokenResponse(access_token=access_token, refresh_token=refresh_token),
        )

    except PasswordValidationError as e:
        logger.warning("Registration failed: password validation error", error=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ValueError as e:
        logger.warning("Registration failed: validation error", error=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/login", response_model=AuthResponse)
@limiter.limit(f"{settings.auth_rate_limit_per_minute}/minute")
async def login(
    request_data: UserLoginRequest, request: Request, db: AsyncSession = Depends(get_db)
) -> AuthResponse:
    """Authenticate user and return tokens.

    Args:
        request_data: User login request
        request: HTTP request (for rate limiting)
        db: Database session

    Returns:
        User information and authentication tokens

    Raises:
        HTTPException: If authentication fails
    """
    logger.info("User login request", email=request_data.email)

    auth_service = AuthService(db)

    try:
        # Authenticate user
        user = await auth_service.authenticate_user(
            email=request_data.email, password=request_data.password
        )

        # Generate tokens
        access_token = auth_service.create_access_token(user.id)
        refresh_token = auth_service.create_refresh_token(user.id)

        logger.info("User logged in successfully", user_id=str(user.id), email=user.email)

        return AuthResponse(
            user=UserResponse(
                id=user.id,
                email=user.email,
                first_name=user.first_name,
                last_name=user.last_name,
                created_at=user.created_at,
            ),
            tokens=TokenResponse(access_token=access_token, refresh_token=refresh_token),
        )

    except AuthenticationError as e:
        logger.warning("Login failed: authentication error", error=str(e))
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit(f"{settings.auth_rate_limit_per_minute}/minute")
async def refresh_token(
    request_data: TokenRefreshRequest, request: Request, db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    """Refresh access token using refresh token.

    Args:
        request_data: Token refresh request
        request: HTTP request (for rate limiting)
        db: Database session

    Returns:
        New access and refresh tokens

    Raises:
        HTTPException: If token refresh fails
    """
    logger.info("Token refresh request")

    auth_service = AuthService(db)

    try:
        # Refresh tokens
        access_token, refresh_token = await auth_service.refresh_access_token(
            request_data.refresh_token
        )

        logger.info("Tokens refreshed successfully")

        return TokenResponse(access_token=access_token, refresh_token=refresh_token)

    except TokenError as e:
        logger.warning("Token refresh failed", error=str(e))
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.post("/logout", response_model=MessageResponse)
async def logout(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Logout user by blacklisting their token.

    Args:
        token: JWT access token
        db: Database session

    Returns:
        Success message
    """
    logger.info("User logout request")

    auth_service = AuthService(db)
    await auth_service.blacklist_token(token)

    return MessageResponse(
        message="Logged out successfully. Token has been revoked."
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)
) -> UserResponse:
    """Get current authenticated user.

    Args:
        token: JWT access token
        db: Database session

    Returns:
        User profile

    Raises:
        HTTPException: If token is invalid or user not found
    """
    auth_service = AuthService(db)

    try:
        user = await auth_service.get_current_user(token)

        return UserResponse(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            created_at=user.created_at,
        )

    except (AuthenticationError, TokenError) as e:
        logger.warning("Get user me failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
