"""
End-to-end integration tests for complete user workflows.

These tests verify that all components work together correctly
by testing complete user journeys through the system.
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.user import User


class TestUserRegistrationAndAuthFlow:
    """Test complete user registration and authentication flow."""
    
    @pytest.mark.asyncio
    async def test_complete_auth_flow(self, client: AsyncClient):
        """Test user registration, login, token refresh, and logout."""
        # 1. Register a new user
        register_data = {
            "email": "e2e_user@example.com",
            "password": "SecurePass123!",
            "first_name": "E2E",
            "last_name": "User"
        }
        response = await client.post("/api/auth/register", json=register_data)
        assert response.status_code == 201
        user_data = response.json()
        assert user_data["user"]["email"] == register_data["email"]
        assert "access_token" in user_data["tokens"]
        assert "refresh_token" in user_data["tokens"]
        
        # 2. Login with credentials
        login_data = {
            "email": register_data["email"],
            "password": register_data["password"]
        }
        response = await client.post("/api/auth/login", json=login_data)
        assert response.status_code == 200
        tokens = response.json()
        access_token = tokens["tokens"]["access_token"]
        refresh_token = tokens["tokens"]["refresh_token"]
        
        # 3. Access protected endpoint with access token
        headers = {"Authorization": f"Bearer {access_token}"}
        response = await client.get("/api/transactions", headers=headers)
        assert response.status_code == 200
        
        # 4. Refresh access token
        response = await client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token}
        )
        assert response.status_code == 200
        new_tokens = response.json()
        assert "access_token" in new_tokens["tokens"]
        
        # 5. Logout
        response = await client.post("/api/auth/logout", headers=headers)
        assert response.status_code == 200


class TestTransactionManagementFlow:
    """Test complete transaction management workflow."""
    
    @pytest.mark.asyncio
    async def test_transaction_crud_flow(
        self,
        client: AsyncClient,
        test_user: User,
        auth_headers: dict
    ):
        """Test creating, reading, updating, and deleting transactions."""
        # 1. Create a transaction
        transaction_data = {
            "amount": 50.00,
            "description": "Grocery shopping at Whole Foods",
            "transaction_type": "expense",
            "date": datetime.now().isoformat()
        }
        response = await client.post(
            "/api/transactions",
            json=transaction_data,
            headers=auth_headers
        )
        assert response.status_code == 201
        transaction = response.json()
        transaction_id = transaction["id"]
        
        # Verify auto-categorization worked
        assert transaction["category"] is not None
        assert transaction["category"] in ["Groceries", "Food & Dining"]
        
        # 2. Read the transaction
        response = await client.get(
            f"/api/transactions/{transaction_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        fetched_transaction = response.json()
        assert fetched_transaction["id"] == transaction_id
        
        # 3. List transactions
        response = await client.get("/api/transactions", headers=auth_headers)
        assert response.status_code == 200
        transactions = response.json()
        assert len(transactions) >= 1
        
        # 4. Update the transaction
        update_data = {
            "amount": 55.00,
            "description": "Updated: Grocery shopping"
        }
        response = await client.put(
            f"/api/transactions/{transaction_id}",
            json=update_data,
            headers=auth_headers
        )
        assert response.status_code == 200
        updated_transaction = response.json()
        assert updated_transaction["amount"] == 55.00
        
        # 5. Delete the transaction
        response = await client.delete(
            f"/api/transactions/{transaction_id}",
            headers=auth_headers
        )
        assert response.status_code == 204
        
        # Verify deletion
        response = await client.get(
            f"/api/transactions/{transaction_id}",
            headers=auth_headers
        )
        assert response.status_code == 404


class TestBudgetManagementFlow:
    """Test complete budget management workflow."""
    
    @pytest.mark.asyncio
    async def test_budget_lifecycle(
        self,
        client: AsyncClient,
        test_user: User,
        auth_headers: dict
    ):
        """Test creating budget, tracking progress, and optimization."""
        # 1. Create transactions for budget tracking
        transactions = [
            {
                "amount": 300.00,
                "description": "Grocery shopping",
                "transaction_type": "expense",
                "category": "Groceries",
                "date": datetime.now().isoformat()
            },
            {
                "amount": 150.00,
                "description": "Restaurant dinner",
                "transaction_type": "expense",
                "category": "Dining",
                "date": datetime.now().isoformat()
            }
        ]
        
        for txn_data in transactions:
            response = await client.post(
                "/api/transactions",
                json=txn_data,
                headers=auth_headers
            )
            assert response.status_code == 201
        
        # 2. Create a budget
        budget_data = {
            "name": "Monthly Budget",
            "period_start": datetime.now().replace(day=1).isoformat(),
            "period_end": (datetime.now().replace(day=1) + timedelta(days=31)).isoformat(),
            "allocations": {
                "Groceries": 400.00,
                "Dining": 200.00,
                "Transportation": 150.00
            }
        }
        response = await client.post(
            "/api/budgets",
            json=budget_data,
            headers=auth_headers
        )
        assert response.status_code == 201
        budget = response.json()
        budget_id = budget["id"]
        
        # 3. Check budget progress
        response = await client.get(
            f"/api/budgets/{budget_id}/progress",
            headers=auth_headers
        )
        assert response.status_code == 200
        progress = response.json()
        
        # Verify progress tracking
        assert "categories" in progress
        assert "Groceries" in progress["categories"]
        assert progress["categories"]["Groceries"]["spent"] == 300.00
        assert progress["categories"]["Groceries"]["allocated"] == 400.00
        
        # 4. Get optimization suggestions
        response = await client.post(
            f"/api/budgets/{budget_id}/optimize",
            headers=auth_headers
        )
        assert response.status_code == 200
        suggestions = response.json()
        assert "suggestions" in suggestions
        
        # 5. Apply optimization (if suggestions exist)
        if suggestions["suggestions"]:
            response = await client.put(
                f"/api/budgets/{budget_id}/apply-optimization",
                json={"approved": True},
                headers=auth_headers
            )
            assert response.status_code == 200


class TestGoalTrackingFlow:
    """Test complete financial goal tracking workflow."""
    
    @pytest.mark.asyncio
    async def test_goal_lifecycle(
        self,
        client: AsyncClient,
        test_user: User,
        auth_headers: dict
    ):
        """Test creating goal, tracking progress, and achievement."""
        # 1. Create a financial goal
        goal_data = {
            "name": "Emergency Fund",
            "target_amount": 5000.00,
            "current_amount": 1000.00,
            "category": "Savings",
            "deadline": (datetime.now() + timedelta(days=180)).isoformat()
        }
        response = await client.post(
            "/api/goals",
            json=goal_data,
            headers=auth_headers
        )
        assert response.status_code == 201
        goal = response.json()
        goal_id = goal["id"]
        
        # 2. Check initial progress
        response = await client.get(
            f"/api/goals/{goal_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        goal_data = response.json()
        assert goal_data["progress_percentage"] == 20.0  # 1000/5000
        
        # 3. Update goal progress
        response = await client.put(
            f"/api/goals/{goal_id}/progress",
            json={"amount": 500.00},
            headers=auth_headers
        )
        assert response.status_code == 200
        updated_goal = response.json()
        assert updated_goal["current_amount"] == 1500.00
        
        # 4. Check for risk alerts
        response = await client.get(
            f"/api/goals/{goal_id}/risk-alerts",
            headers=auth_headers
        )
        assert response.status_code == 200
        alerts = response.json()
        assert "alerts" in alerts
        
        # 5. Update goal to achieved status
        response = await client.put(
            f"/api/goals/{goal_id}/progress",
            json={"amount": 3500.00},  # Total: 5000
            headers=auth_headers
        )
        assert response.status_code == 200
        achieved_goal = response.json()
        assert achieved_goal["status"] == "achieved"


class TestAdviceGenerationFlow:
    """Test personalized advice generation workflow."""
    
    @pytest.mark.asyncio
    async def test_advice_generation(
        self,
        client: AsyncClient,
        test_user: User,
        auth_headers: dict
    ):
        """Test getting personalized financial advice."""
        # 1. Create some transactions
        transactions = [
            {
                "amount": 500.00,
                "description": "Expensive restaurant",
                "transaction_type": "expense",
                "category": "Dining",
                "date": datetime.now().isoformat()
            },
            {
                "amount": 3000.00,
                "description": "Monthly salary",
                "transaction_type": "income",
                "category": "Salary",
                "date": datetime.now().isoformat()
            }
        ]
        
        for txn_data in transactions:
            await client.post(
                "/api/transactions",
                json=txn_data,
                headers=auth_headers
            )
        
        # 2. Get personalized advice
        response = await client.get(
            "/api/advice",
            headers=auth_headers
        )
        assert response.status_code == 200
        advice = response.json()
        assert "advice" in advice
        assert len(advice["advice"]) > 0
        
        # Verify advice structure
        for item in advice["advice"]:
            assert "message" in item
            assert "priority" in item
            assert "explanation" in item
        
        # 3. Get spending alerts
        response = await client.get(
            "/api/advice/spending-alerts",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        # 4. Get savings opportunities
        response = await client.get(
            "/api/advice/savings-opportunities",
            headers=auth_headers
        )
        assert response.status_code == 200


class TestReportingFlow:
    """Test financial reporting workflow."""
    
    @pytest.mark.asyncio
    async def test_report_generation_and_export(
        self,
        client: AsyncClient,
        test_user: User,
        auth_headers: dict
    ):
        """Test generating and exporting financial reports."""
        # 1. Create transactions for reporting
        transactions = [
            {
                "amount": 2000.00,
                "description": "Salary",
                "transaction_type": "income",
                "category": "Salary",
                "date": datetime.now().isoformat()
            },
            {
                "amount": 500.00,
                "description": "Rent",
                "transaction_type": "expense",
                "category": "Housing",
                "date": datetime.now().isoformat()
            },
            {
                "amount": 200.00,
                "description": "Groceries",
                "transaction_type": "expense",
                "category": "Groceries",
                "date": datetime.now().isoformat()
            }
        ]
        
        for txn_data in transactions:
            await client.post(
                "/api/transactions",
                json=txn_data,
                headers=auth_headers
            )
        
        # 2. Generate a report
        report_data = {
            "start_date": (datetime.now() - timedelta(days=30)).isoformat(),
            "end_date": datetime.now().isoformat()
        }
        response = await client.post(
            "/api/reports/generate",
            json=report_data,
            headers=auth_headers
        )
        assert response.status_code == 200
        report = response.json()
        
        # Verify report structure
        assert "total_income" in report
        assert "total_expenses" in report
        assert "net_savings" in report
        assert "savings_rate" in report
        assert "expense_breakdown" in report
        assert "income_breakdown" in report
        
        # Verify calculations
        assert report["total_income"] == 2000.00
        assert report["total_expenses"] == 700.00
        assert report["net_savings"] == 1300.00
        
        # 3. Export report to CSV
        response = await client.get(
            "/api/export/transactions",
            params={
                "start_date": (datetime.now() - timedelta(days=30)).isoformat(),
                "end_date": datetime.now().isoformat()
            },
            headers=auth_headers
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"


class TestFileImportFlow:
    """Test file import workflow."""
    
    @pytest.mark.asyncio
    async def test_file_import_workflow(
        self,
        client: AsyncClient,
        test_user: User,
        auth_headers: dict
    ):
        """Test importing transactions from CSV file."""
        # 1. Download template
        response = await client.get(
            "/api/import/template",
            params={"format": "csv"},
            headers=auth_headers
        )
        assert response.status_code == 200
        
        # 2. Create CSV content
        csv_content = """date,description,amount,type,category
2024-01-15,Grocery Store,50.00,expense,Groceries
2024-01-16,Salary Deposit,3000.00,income,Salary
2024-01-17,Gas Station,40.00,expense,Transportation"""
        
        # 3. Import transactions
        files = {"file": ("transactions.csv", csv_content, "text/csv")}
        response = await client.post(
            "/api/import/transactions",
            files=files,
            headers=auth_headers
        )
        assert response.status_code == 200
        result = response.json()
        
        # Verify import results
        assert result["total_transactions"] == 3
        assert result["successful_imports"] >= 2  # At least 2 should succeed
        
        # 4. Verify transactions were created
        response = await client.get("/api/transactions", headers=auth_headers)
        assert response.status_code == 200
        transactions = response.json()
        assert len(transactions) >= 3


class TestPredictionFlow:
    """Test expense prediction workflow."""
    
    @pytest.mark.asyncio
    async def test_expense_forecasting(
        self,
        client: AsyncClient,
        test_user: User,
        auth_headers: dict
    ):
        """Test getting expense forecasts."""
        # 1. Create historical transactions
        base_date = datetime.now() - timedelta(days=90)
        for i in range(12):  # 12 weeks of data
            transaction_date = base_date + timedelta(weeks=i)
            await client.post(
                "/api/transactions",
                json={
                    "amount": 200.00 + (i * 10),  # Increasing trend
                    "description": f"Weekly groceries {i}",
                    "transaction_type": "expense",
                    "category": "Groceries",
                    "date": transaction_date.isoformat()
                },
                headers=auth_headers
            )
        
        # 2. Get expense forecasts
        response = await client.get(
            "/api/predictions",
            params={"periods": 4},
            headers=auth_headers
        )
        
        # Note: May return 200 with empty forecasts if insufficient data
        assert response.status_code in [200, 400]
        
        if response.status_code == 200:
            forecasts = response.json()
            assert "forecasts" in forecasts


class TestCompleteUserJourney:
    """Test a complete user journey through the system."""
    
    @pytest.mark.asyncio
    async def test_complete_user_journey(self, client: AsyncClient):
        """
        Test a complete user journey:
        1. Register
        2. Add transactions
        3. Create budget
        4. Set financial goal
        5. Get advice
        6. Generate report
        """
        # 1. Register
        register_data = {
            "email": "journey_user@example.com",
            "password": "SecurePass123!",
            "first_name": "Journey",
            "last_name": "User"
        }
        response = await client.post("/api/auth/register", json=register_data)
        assert response.status_code == 201
        tokens = response.json()
        headers = {"Authorization": f"Bearer {tokens['tokens']['access_token']}"}
        
        # 2. Add transactions
        transactions = [
            {"amount": 3000.00, "description": "Salary", "transaction_type": "income", "category": "Salary"},
            {"amount": 1000.00, "description": "Rent", "transaction_type": "expense", "category": "Housing"},
            {"amount": 300.00, "description": "Groceries", "transaction_type": "expense", "category": "Groceries"},
            {"amount": 150.00, "description": "Utilities", "transaction_type": "expense", "category": "Utilities"},
        ]
        
        for txn in transactions:
            txn["date"] = datetime.now().isoformat()
            response = await client.post("/api/transactions", json=txn, headers=headers)
            assert response.status_code == 201
        
        # 3. Create budget
        budget_data = {
            "name": "Monthly Budget",
            "period_start": datetime.now().replace(day=1).isoformat(),
            "period_end": (datetime.now().replace(day=1) + timedelta(days=31)).isoformat(),
            "allocations": {
                "Housing": 1200.00,
                "Groceries": 400.00,
                "Utilities": 200.00
            }
        }
        response = await client.post("/api/budgets", json=budget_data, headers=headers)
        assert response.status_code == 201
        budget = response.json()
        
        # 4. Set financial goal
        goal_data = {
            "name": "Vacation Fund",
            "target_amount": 2000.00,
            "current_amount": 0.00,
            "category": "Savings",
            "deadline": (datetime.now() + timedelta(days=180)).isoformat()
        }
        response = await client.post("/api/goals", json=goal_data, headers=headers)
        assert response.status_code == 201
        
        # 5. Get personalized advice
        response = await client.get("/api/advice", headers=headers)
        assert response.status_code == 200
        advice = response.json()
        assert len(advice["advice"]) > 0
        
        # 6. Generate report
        report_data = {
            "start_date": (datetime.now() - timedelta(days=30)).isoformat(),
            "end_date": datetime.now().isoformat()
        }
        response = await client.post("/api/reports/generate", json=report_data, headers=headers)
        assert response.status_code == 200
        report = response.json()
        
        # Verify the journey was successful
        assert report["total_income"] == 3000.00
        assert report["total_expenses"] == 1450.00
        assert report["net_savings"] == 1550.00
        
        # 7. Check budget progress
        response = await client.get(f"/api/budgets/{budget['id']}/progress", headers=headers)
        assert response.status_code == 200
        progress = response.json()
        assert "categories" in progress
