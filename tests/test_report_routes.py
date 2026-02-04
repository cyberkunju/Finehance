"""Tests for report API endpoints."""

import pytest
from datetime import date, timedelta
from decimal import Decimal
from httpx import AsyncClient

from app.models.transaction import Transaction
from app.models.budget import Budget


@pytest.mark.asyncio
class TestReportRoutes:
    """Test report API endpoints."""
    
    async def test_generate_report_basic(
        self, async_client: AsyncClient, test_user, test_db
    ):
        """Test basic report generation."""
        user_id = test_user.id
        
        # Create some transactions
        today = date.today()
        for i in range(5):
            # Income
            income = Transaction(
                user_id=user_id,
                amount=Decimal("1000.00"),
                type="INCOME",
                category="Salary",
                description=f"Income {i}",
                date=today - timedelta(days=i),
                source="MANUAL"
            )
            test_db.add(income)
            
            # Expense
            expense = Transaction(
                user_id=user_id,
                amount=Decimal("50.00"),
                type="EXPENSE",
                category="Groceries",
                description=f"Expense {i}",
                date=today - timedelta(days=i),
                source="MANUAL"
            )
            test_db.add(expense)
        
        await test_db.commit()
        
        # Generate report
        start_date = (today - timedelta(days=30)).isoformat()
        end_date = today.isoformat()
        
        response = await async_client.post(
            "/api/reports/generate",
            json={
                "user_id": str(user_id),
                "start_date": start_date,
                "end_date": end_date,
                "include_budget_analysis": False
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "report_id" in data
        assert data["user_id"] == str(user_id)
        assert data["start_date"] == start_date
        assert data["end_date"] == end_date
        assert "income_summary" in data
        assert "expense_summary" in data
        assert "net_savings" in data
        assert "savings_rate" in data
        assert data["budget_adherence"] is None  # Not requested
    
    async def test_generate_report_with_budget_analysis(
        self, async_client: AsyncClient, test_user, test_db
    ):
        """Test report generation with budget analysis."""
        user_id = test_user.id
        today = date.today()
        
        # Create budget
        budget = Budget(
            user_id=user_id,
            name="Monthly Budget",
            period_start=today.replace(day=1),
            period_end=today,
            allocations={"Groceries": 500.00, "Transport": 200.00}
        )
        test_db.add(budget)
        await test_db.commit()
        await test_db.refresh(budget)
        
        # Create transactions
        for i in range(5):
            transaction = Transaction(
                user_id=user_id,
                amount=Decimal("50.00"),
                type="EXPENSE",
                category="Groceries",
                description=f"Groceries {i}",
                date=today - timedelta(days=i),
                source="MANUAL"
            )
            test_db.add(transaction)
        
        await test_db.commit()
        
        # Generate report with budget analysis
        response = await async_client.post(
            "/api/reports/generate",
            json={
                "user_id": str(user_id),
                "start_date": today.replace(day=1).isoformat(),
                "end_date": today.isoformat(),
                "include_budget_analysis": True,
                "budget_id": str(budget.id)
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["budget_adherence"] is not None
        assert data["budget_adherence"]["budget_id"] == str(budget.id)
        assert data["budget_adherence"]["budget_name"] == "Monthly Budget"
        assert "categories" in data["budget_adherence"]
        assert "overall_adherence" in data["budget_adherence"]
    
    async def test_generate_report_invalid_date_range(
        self, async_client: AsyncClient, test_user, test_db
    ):
        """Test report generation with invalid date range."""
        user_id = test_user.id
        today = date.today()
        
        # Start date after end date
        response = await async_client.post(
            "/api/reports/generate",
            json={
                "user_id": str(user_id),
                "start_date": today.isoformat(),
                "end_date": (today - timedelta(days=30)).isoformat(),
                "include_budget_analysis": False
            }
        )
        
        assert response.status_code == 400
        assert "Start date must be before" in response.json()["detail"]
    
    async def test_generate_report_empty_period(
        self, async_client: AsyncClient, test_user, test_db
    ):
        """Test report generation with no transactions."""
        user_id = test_user.id
        today = date.today()
        
        response = await async_client.post(
            "/api/reports/generate",
            json={
                "user_id": str(user_id),
                "start_date": (today - timedelta(days=30)).isoformat(),
                "end_date": today.isoformat(),
                "include_budget_analysis": False
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return report with zero values
        assert float(data["income_summary"]["total_income"]) == 0
        assert float(data["expense_summary"]["total_expenses"]) == 0
        assert float(data["net_savings"]) == 0
    
    async def test_export_report_csv(
        self, async_client: AsyncClient, test_user, test_db
    ):
        """Test CSV export."""
        user_id = test_user.id
        today = date.today()
        
        # Create transactions
        for i in range(3):
            transaction = Transaction(
                user_id=user_id,
                amount=Decimal("100.00"),
                type="EXPENSE",
                category="Groceries",
                description=f"Test {i}",
                date=today - timedelta(days=i),
                source="MANUAL"
            )
            test_db.add(transaction)
        
        await test_db.commit()
        
        # Export to CSV
        start_date = (today - timedelta(days=30)).isoformat()
        end_date = today.isoformat()
        
        response = await async_client.post(
            f"/api/reports/export/csv?user_id={user_id}&start_date={start_date}&end_date={end_date}&include_budget_analysis=false"
        )
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        assert "attachment" in response.headers["content-disposition"]
        assert ".csv" in response.headers["content-disposition"]
        
        # Check CSV content
        content = response.text
        assert "Financial Report" in content or "Income" in content
    
    async def test_export_report_pdf(
        self, async_client: AsyncClient, test_user, test_db
    ):
        """Test PDF export."""
        user_id = test_user.id
        today = date.today()
        
        # Create transactions
        for i in range(3):
            transaction = Transaction(
                user_id=user_id,
                amount=Decimal("100.00"),
                type="EXPENSE",
                category="Groceries",
                description=f"Test {i}",
                date=today - timedelta(days=i),
                source="MANUAL"
            )
            test_db.add(transaction)
        
        await test_db.commit()
        
        # Export to PDF
        start_date = (today - timedelta(days=30)).isoformat()
        end_date = today.isoformat()
        
        response = await async_client.post(
            f"/api/reports/export/pdf?user_id={user_id}&start_date={start_date}&end_date={end_date}&include_budget_analysis=false"
        )
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert "attachment" in response.headers["content-disposition"]
        assert ".pdf" in response.headers["content-disposition"]
        
        # Check PDF content (starts with PDF magic bytes)
        content = response.content
        assert content.startswith(b"%PDF")
    
    async def test_export_csv_invalid_date_format(
        self, async_client: AsyncClient, test_user, test_db
    ):
        """Test CSV export with invalid date format."""
        user_id = test_user.id
        
        response = await async_client.post(
            f"/api/reports/export/csv?user_id={user_id}&start_date=invalid&end_date=2024-01-01&include_budget_analysis=false"
        )
        
        assert response.status_code == 400
        assert "Invalid date format" in response.json()["detail"]
    
    async def test_export_pdf_invalid_date_range(
        self, async_client: AsyncClient, test_user, test_db
    ):
        """Test PDF export with invalid date range."""
        user_id = test_user.id
        today = date.today()
        
        response = await async_client.post(
            f"/api/reports/export/pdf?user_id={user_id}&start_date={today.isoformat()}&end_date={(today - timedelta(days=30)).isoformat()}&include_budget_analysis=false"
        )
        
        assert response.status_code == 400
        assert "Start date must be before" in response.json()["detail"]
    
    async def test_generate_report_with_spending_changes(
        self, async_client: AsyncClient, test_user, test_db
    ):
        """Test report includes spending pattern changes."""
        user_id = test_user.id
        today = date.today()
        
        # Create transactions in current period
        for i in range(5):
            transaction = Transaction(
                user_id=user_id,
                amount=Decimal("100.00"),
                type="EXPENSE",
                category="Groceries",
                description=f"Current {i}",
                date=today - timedelta(days=i),
                source="MANUAL"
            )
            test_db.add(transaction)
        
        # Create transactions in previous period (lower spending)
        for i in range(5):
            transaction = Transaction(
                user_id=user_id,
                amount=Decimal("50.00"),
                type="EXPENSE",
                category="Groceries",
                description=f"Previous {i}",
                date=today - timedelta(days=40 + i),
                source="MANUAL"
            )
            test_db.add(transaction)
        
        await test_db.commit()
        
        # Generate report
        response = await async_client.post(
            "/api/reports/generate",
            json={
                "user_id": str(user_id),
                "start_date": (today - timedelta(days=30)).isoformat(),
                "end_date": today.isoformat(),
                "include_budget_analysis": False
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should include spending changes
        assert "spending_changes" in data
        assert isinstance(data["spending_changes"], list)
    
    async def test_export_csv_with_budget_analysis(
        self, async_client: AsyncClient, test_user, test_db
    ):
        """Test CSV export with budget analysis."""
        user_id = test_user.id
        today = date.today()
        
        # Create budget
        budget = Budget(
            user_id=user_id,
            name="Test Budget",
            period_start=today.replace(day=1),
            period_end=today,
            allocations={"Groceries": 300.00}
        )
        test_db.add(budget)
        await test_db.commit()
        await test_db.refresh(budget)
        
        # Create transactions
        for i in range(3):
            transaction = Transaction(
                user_id=user_id,
                amount=Decimal("50.00"),
                type="EXPENSE",
                category="Groceries",
                description=f"Test {i}",
                date=today - timedelta(days=i),
                source="MANUAL"
            )
            test_db.add(transaction)
        
        await test_db.commit()
        
        # Export with budget analysis
        response = await async_client.post(
            f"/api/reports/export/csv?user_id={user_id}&start_date={today.replace(day=1).isoformat()}&end_date={today.isoformat()}&include_budget_analysis=true&budget_id={budget.id}"
        )
        
        assert response.status_code == 200
        content = response.text
        
        # Should include budget information
        assert "Budget" in content or "Groceries" in content
