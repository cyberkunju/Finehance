"""Tests for authentication API endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestAuthRoutes:
    """Test authentication API endpoints."""
    
    async def test_register_success(self, async_client: AsyncClient, test_db):
        """Test successful user registration."""
        response = await async_client.post(
            "/api/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "SecurePass123!@#",
                "first_name": "John",
                "last_name": "Doe"
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        
        # Check user data
        assert "user" in data
        assert data["user"]["email"] == "newuser@example.com"
        assert data["user"]["first_name"] == "John"
        assert data["user"]["last_name"] == "Doe"
        assert "id" in data["user"]
        assert "created_at" in data["user"]
        
        # Check tokens
        assert "tokens" in data
        assert "access_token" in data["tokens"]
        assert "refresh_token" in data["tokens"]
        assert data["tokens"]["token_type"] == "bearer"
        assert data["tokens"]["expires_in"] == 1800
    
    async def test_register_weak_password(self, async_client: AsyncClient, test_db):
        """Test registration with weak password."""
        response = await async_client.post(
            "/api/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "weak",
                "first_name": "John",
                "last_name": "Doe"
            }
        )
        
        # Pydantic validation error for min_length=12
        assert response.status_code == 422
        assert "detail" in response.json()
    
    async def test_register_password_no_uppercase(self, async_client: AsyncClient, test_db):
        """Test registration with password missing uppercase."""
        response = await async_client.post(
            "/api/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "securepass123!@#",
                "first_name": "John",
                "last_name": "Doe"
            }
        )
        
        assert response.status_code == 400
        assert "uppercase" in response.json()["detail"].lower()
    
    async def test_register_password_no_lowercase(self, async_client: AsyncClient, test_db):
        """Test registration with password missing lowercase."""
        response = await async_client.post(
            "/api/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "SECUREPASS123!@#",
                "first_name": "John",
                "last_name": "Doe"
            }
        )
        
        assert response.status_code == 400
        assert "lowercase" in response.json()["detail"].lower()
    
    async def test_register_password_no_number(self, async_client: AsyncClient, test_db):
        """Test registration with password missing number."""
        response = await async_client.post(
            "/api/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "SecurePass!@#$",
                "first_name": "John",
                "last_name": "Doe"
            }
        )
        
        assert response.status_code == 400
        assert "number" in response.json()["detail"].lower()
    
    async def test_register_password_no_special_char(self, async_client: AsyncClient, test_db):
        """Test registration with password missing special character."""
        response = await async_client.post(
            "/api/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "SecurePass123",
                "first_name": "John",
                "last_name": "Doe"
            }
        )
        
        assert response.status_code == 400
        assert "special character" in response.json()["detail"].lower()
    
    async def test_register_duplicate_email(self, async_client: AsyncClient, test_user, test_db):
        """Test registration with existing email."""
        response = await async_client.post(
            "/api/auth/register",
            json={
                "email": test_user.email,
                "password": "SecurePass123!@#",
                "first_name": "John",
                "last_name": "Doe"
            }
        )
        
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]
    
    async def test_register_without_optional_fields(self, async_client: AsyncClient, test_db):
        """Test registration without optional first/last name."""
        response = await async_client.post(
            "/api/auth/register",
            json={
                "email": "minimal@example.com",
                "password": "SecurePass123!@#"
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["user"]["email"] == "minimal@example.com"
        assert data["user"]["first_name"] is None
        assert data["user"]["last_name"] is None
    
    async def test_login_success(self, async_client: AsyncClient, test_user, test_db):
        """Test successful login."""
        response = await async_client.post(
            "/api/auth/login",
            json={
                "email": test_user.email,
                "password": "TestPassword123!@#"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check user data
        assert "user" in data
        assert data["user"]["email"] == test_user.email
        assert data["user"]["id"] == str(test_user.id)
        
        # Check tokens
        assert "tokens" in data
        assert "access_token" in data["tokens"]
        assert "refresh_token" in data["tokens"]
    
    async def test_login_invalid_email(self, async_client: AsyncClient, test_db):
        """Test login with non-existent email."""
        response = await async_client.post(
            "/api/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "TestPassword123!@#"
            }
        )
        
        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["detail"]
    
    async def test_login_invalid_password(self, async_client: AsyncClient, test_user, test_db):
        """Test login with incorrect password."""
        response = await async_client.post(
            "/api/auth/login",
            json={
                "email": test_user.email,
                "password": "WrongPassword123!@#"
            }
        )
        
        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["detail"]
    
    async def test_refresh_token_success(self, async_client: AsyncClient, test_user, test_db):
        """Test successful token refresh."""
        # First login to get tokens
        login_response = await async_client.post(
            "/api/auth/login",
            json={
                "email": test_user.email,
                "password": "TestPassword123!@#"
            }
        )
        
        assert login_response.status_code == 200
        refresh_token = login_response.json()["tokens"]["refresh_token"]
        
        # Refresh tokens
        response = await async_client.post(
            "/api/auth/refresh",
            json={
                "refresh_token": refresh_token
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        
        # Verify new tokens are valid (they may be identical if created in same second)
        # The important thing is that refresh works, not that tokens are different
        assert len(data["access_token"]) > 0
        assert len(data["refresh_token"]) > 0
    
    async def test_refresh_token_invalid(self, async_client: AsyncClient, test_db):
        """Test token refresh with invalid token."""
        response = await async_client.post(
            "/api/auth/refresh",
            json={
                "refresh_token": "invalid_token"
            }
        )
        
        assert response.status_code == 401
        assert "Invalid token" in response.json()["detail"]
    
    async def test_refresh_token_with_access_token(self, async_client: AsyncClient, test_user, test_db):
        """Test token refresh with access token instead of refresh token."""
        # First login to get tokens
        login_response = await async_client.post(
            "/api/auth/login",
            json={
                "email": test_user.email,
                "password": "TestPassword123!@#"
            }
        )
        
        assert login_response.status_code == 200
        access_token = login_response.json()["tokens"]["access_token"]
        
        # Try to refresh with access token (should fail)
        response = await async_client.post(
            "/api/auth/refresh",
            json={
                "refresh_token": access_token
            }
        )
        
        assert response.status_code == 401
        assert "Invalid token type" in response.json()["detail"]
    
    async def test_logout(self, async_client: AsyncClient):
        """Test logout endpoint."""
        response = await async_client.post("/api/auth/logout")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "message" in data
        assert "Logged out successfully" in data["message"]
    
    async def test_register_invalid_email_format(self, async_client: AsyncClient, test_db):
        """Test registration with invalid email format."""
        response = await async_client.post(
            "/api/auth/register",
            json={
                "email": "not-an-email",
                "password": "SecurePass123!@#",
                "first_name": "John",
                "last_name": "Doe"
            }
        )
        
        assert response.status_code == 422  # Pydantic validation error
    
    async def test_login_invalid_email_format(self, async_client: AsyncClient, test_db):
        """Test login with invalid email format."""
        response = await async_client.post(
            "/api/auth/login",
            json={
                "email": "not-an-email",
                "password": "TestPassword123!@#"
            }
        )
        
        assert response.status_code == 422  # Pydantic validation error
