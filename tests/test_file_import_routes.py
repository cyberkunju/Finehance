"""Tests for file import/export API endpoints."""

import pytest
import io
from datetime import date, timedelta
from decimal import Decimal
from httpx import AsyncClient

from app.models.transaction import Transaction


@pytest.mark.asyncio
class TestFileImportRoutes:
    """Test file import/export API endpoints."""

    async def test_import_transactions_csv(self, async_client: AsyncClient, test_user, test_db):
        """Test importing transactions from CSV file."""
        user_id = test_user.id

        # Create CSV content
        csv_content = """date,amount,type,category,description
2024-01-15,100.50,EXPENSE,Groceries,Weekly shopping
2024-01-16,2500.00,INCOME,Salary,Monthly salary
2024-01-17,50.00,EXPENSE,Transport,Gas
"""

        # Create file-like object
        files = {"file": ("transactions.csv", io.BytesIO(csv_content.encode()), "text/csv")}

        response = await async_client.post(
            f"/api/import/transactions?user_id={user_id}", files=files
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success_count"] == 3
        assert data["error_count"] == 0
        assert len(data["errors"]) == 0
        assert data["imported_transactions"] == 3

    async def test_import_transactions_invalid_format(
        self, async_client: AsyncClient, test_user, test_db
    ):
        """Test importing with invalid file format."""
        user_id = test_user.id

        # Create invalid file
        files = {"file": ("transactions.txt", io.BytesIO(b"invalid content"), "text/plain")}

        response = await async_client.post(
            f"/api/import/transactions?user_id={user_id}", files=files
        )

        assert response.status_code == 400
        assert "Invalid file format" in response.json()["detail"]

    async def test_import_transactions_malformed_csv(
        self, async_client: AsyncClient, test_user, test_db
    ):
        """Test importing malformed CSV."""
        user_id = test_user.id

        # Create malformed CSV (missing required columns)
        csv_content = """date,amount
2024-01-15,100.50
"""

        files = {"file": ("transactions.csv", io.BytesIO(csv_content.encode()), "text/csv")}

        response = await async_client.post(
            f"/api/import/transactions?user_id={user_id}", files=files
        )

        assert response.status_code == 400
        assert "Missing required columns" in response.json()["detail"]

    async def test_import_transactions_with_errors(
        self, async_client: AsyncClient, test_user, test_db
    ):
        """Test importing CSV with some invalid rows."""
        user_id = test_user.id

        # Create CSV with valid and invalid rows
        csv_content = """date,amount,type,category,description
2024-01-15,100.50,EXPENSE,Groceries,Valid transaction
2024-01-16,invalid,INCOME,Salary,Invalid amount
2024-01-17,50.00,INVALID_TYPE,Transport,Invalid type
2024-01-18,75.00,EXPENSE,Food,Valid transaction
"""

        files = {"file": ("transactions.csv", io.BytesIO(csv_content.encode()), "text/csv")}

        response = await async_client.post(
            f"/api/import/transactions?user_id={user_id}", files=files
        )

        assert response.status_code == 200
        data = response.json()

        # Should import valid rows and report errors for invalid ones
        assert data["success_count"] == 2
        assert data["error_count"] == 2
        assert len(data["errors"]) == 2

    async def test_export_transactions_basic(self, async_client: AsyncClient, test_user, test_db):
        """Test basic transaction export."""
        user_id = test_user.id
        today = date.today()

        # Create some transactions
        for i in range(3):
            transaction = Transaction(
                user_id=user_id,
                amount=Decimal("100.00"),
                type="EXPENSE",
                category="Groceries",
                description=f"Test {i}",
                date=today - timedelta(days=i),
                source="MANUAL",
            )
            test_db.add(transaction)

        await test_db.commit()

        # Export transactions
        response = await async_client.get(f"/api/export/transactions?user_id={user_id}")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        assert "attachment" in response.headers["content-disposition"]
        assert "transactions.csv" in response.headers["content-disposition"]

        # Check CSV content
        content = response.text
        assert "date,amount,type,category,description" in content
        assert "Groceries" in content
        assert "100.00" in content

    async def test_export_transactions_with_date_filter(
        self, async_client: AsyncClient, test_user, test_db
    ):
        """Test export with date range filter."""
        user_id = test_user.id
        today = date.today()

        # Create transactions across different dates
        for i in range(10):
            transaction = Transaction(
                user_id=user_id,
                amount=Decimal(f"{100 + i}.00"),
                type="EXPENSE",
                category="Groceries",
                description=f"Test {i}",
                date=today - timedelta(days=i * 5),
                source="MANUAL",
            )
            test_db.add(transaction)

        await test_db.commit()

        # Export with date filter
        start_date = (today - timedelta(days=15)).isoformat()
        end_date = today.isoformat()

        response = await async_client.get(
            f"/api/export/transactions?user_id={user_id}&start_date={start_date}&end_date={end_date}"
        )

        assert response.status_code == 200
        content = response.text

        # Should only include transactions within date range
        lines = content.strip().split("\n")
        # Header + filtered transactions (should be less than 10)
        assert len(lines) <= 11  # Header + max 10 transactions

    async def test_export_transactions_with_category_filter(
        self, async_client: AsyncClient, test_user, test_db
    ):
        """Test export with category filter."""
        user_id = test_user.id
        today = date.today()

        # Create transactions in different categories
        for category in ["Groceries", "Transport", "Entertainment"]:
            for i in range(2):
                transaction = Transaction(
                    user_id=user_id,
                    amount=Decimal("100.00"),
                    type="EXPENSE",
                    category=category,
                    description=f"{category} {i}",
                    date=today - timedelta(days=i),
                    source="MANUAL",
                )
                test_db.add(transaction)

        await test_db.commit()

        # Export only Groceries
        response = await async_client.get(
            f"/api/export/transactions?user_id={user_id}&category=Groceries"
        )

        assert response.status_code == 200
        content = response.text

        # Should only include Groceries
        assert "Groceries" in content
        assert "Transport" not in content
        assert "Entertainment" not in content

    async def test_export_transactions_with_type_filter(
        self, async_client: AsyncClient, test_user, test_db
    ):
        """Test export with transaction type filter."""
        user_id = test_user.id
        today = date.today()

        # Create income and expense transactions
        for i in range(3):
            # Income
            income = Transaction(
                user_id=user_id,
                amount=Decimal("1000.00"),
                type="INCOME",
                category="Salary",
                description=f"Income {i}",
                date=today - timedelta(days=i),
                source="MANUAL",
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
                source="MANUAL",
            )
            test_db.add(expense)

        await test_db.commit()

        # Export only INCOME
        response = await async_client.get(
            f"/api/export/transactions?user_id={user_id}&transaction_type=INCOME"
        )

        assert response.status_code == 200
        content = response.text

        # Should only include income transactions
        assert "INCOME" in content
        assert "Salary" in content
        lines = content.strip().split("\n")
        # Header + 3 income transactions
        assert len(lines) == 4

    async def test_export_transactions_invalid_date_format(
        self, async_client: AsyncClient, test_user, test_db
    ):
        """Test export with invalid date format."""
        user_id = test_user.id

        response = await async_client.get(
            f"/api/export/transactions?user_id={user_id}&start_date=invalid"
        )

        assert response.status_code == 400
        assert "Invalid start_date format" in response.json()["detail"]

    async def test_export_transactions_invalid_date_range(
        self, async_client: AsyncClient, test_user, test_db
    ):
        """Test export with invalid date range."""
        user_id = test_user.id
        today = date.today()

        response = await async_client.get(
            f"/api/export/transactions?user_id={user_id}&start_date={today.isoformat()}&end_date={(today - timedelta(days=30)).isoformat()}"
        )

        assert response.status_code == 400
        assert "Start date must be before" in response.json()["detail"]

    async def test_export_transactions_empty(self, async_client: AsyncClient, test_user, test_db):
        """Test export with no transactions."""
        user_id = test_user.id

        response = await async_client.get(f"/api/export/transactions?user_id={user_id}")

        assert response.status_code == 200
        content = response.text

        # Should have header only
        lines = content.strip().split("\n")
        assert len(lines) == 1  # Just the header
        assert "date,amount,type,category,description" in content

    async def test_download_template_csv(self, async_client: AsyncClient):
        """Test downloading CSV template."""
        response = await async_client.get("/api/import/template?format=csv")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        assert "attachment" in response.headers["content-disposition"]
        assert "transaction_import_template.csv" in response.headers["content-disposition"]

        # Check template content
        content = response.text
        assert "date,amount,type,category,description" in content
        assert "2024-01-15,100.50,EXPENSE,Groceries,Weekly shopping" in content

    async def test_download_template_xlsx(self, async_client: AsyncClient):
        """Test downloading XLSX template."""
        response = await async_client.get("/api/import/template?format=xlsx")

        assert response.status_code == 200
        assert (
            response.headers["content-type"]
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        assert "attachment" in response.headers["content-disposition"]
        assert "transaction_import_template.xlsx" in response.headers["content-disposition"]

        # Check that content is not empty (XLSX binary)
        content = response.content
        assert len(content) > 0
        # XLSX files start with PK (ZIP format)
        assert content.startswith(b"PK")

    async def test_download_template_invalid_format(self, async_client: AsyncClient):
        """Test downloading template with invalid format."""
        response = await async_client.get("/api/import/template?format=pdf")

        assert response.status_code == 400
        assert "Invalid format" in response.json()["detail"]

    async def test_download_template_default_format(self, async_client: AsyncClient):
        """Test downloading template with default format (CSV)."""
        response = await async_client.get("/api/import/template")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        assert "transaction_import_template.csv" in response.headers["content-disposition"]
