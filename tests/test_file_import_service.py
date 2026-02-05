"""Tests for file import service."""

import pytest
from datetime import datetime, date
from decimal import Decimal
from pathlib import Path
import tempfile
import io

from app.services.file_import_service import FileImportService, FileType, ParsedTransaction


@pytest.mark.asyncio
class TestFileImportService:
    """Test suite for FileImportService."""

    async def test_parse_csv_file_success(self, db_session):
        """Test parsing a valid CSV file."""
        service = FileImportService(db_session)

        # Create temporary CSV file
        csv_content = """Date,Description,Amount,Category,Type
01/15/2024,Grocery Store,-125.50,Groceries,EXPENSE
01/16/2024,Salary Deposit,3000.00,Income,INCOME
01/17/2024,Gas Station,-45.00,Transportation,EXPENSE"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_path = f.name

        try:
            # Parse file
            result = service.parse_file(temp_path, FileType.CSV)

            # Verify results
            assert result.total_rows == 3
            assert result.valid_rows == 3
            assert len(result.transactions) == 3
            assert len(result.errors) == 0
            assert result.success_rate == 100.0

            # Verify first transaction
            tx1 = result.transactions[0]
            assert tx1.date == datetime(2024, 1, 15)
            assert tx1.description == "Grocery Store"
            assert tx1.amount == Decimal("125.50")
            assert tx1.category == "Groceries"
            assert tx1.type == "EXPENSE"

            # Verify second transaction (income)
            tx2 = result.transactions[1]
            assert tx2.type == "INCOME"
            assert tx2.amount == Decimal("3000.00")

        finally:
            Path(temp_path).unlink()

    async def test_parse_csv_with_auto_column_detection(self, db_session):
        """Test CSV parsing with automatic column detection."""
        service = FileImportService(db_session)

        # CSV with different column names
        csv_content = """transaction_date,desc,trans_amount
01/15/2024,Coffee Shop,-5.50
01/16/2024,Bookstore,-25.00"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_path = f.name

        try:
            # Parse without column mapping (should auto-detect)
            result = service.parse_file(temp_path, FileType.CSV)

            assert result.valid_rows == 2
            assert result.transactions[0].description == "Coffee Shop"
            assert result.transactions[0].amount == Decimal("5.50")

        finally:
            Path(temp_path).unlink()

    async def test_parse_csv_with_custom_column_mapping(self, db_session):
        """Test CSV parsing with custom column mapping."""
        service = FileImportService(db_session)

        csv_content = """MyDate,MyDesc,MyAmount
01/15/2024,Restaurant,-67.80
01/16/2024,Grocery,-125.00"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_path = f.name

        try:
            # Parse with custom mapping
            column_mapping = {"date": "MyDate", "description": "MyDesc", "amount": "MyAmount"}
            result = service.parse_file(temp_path, FileType.CSV, column_mapping)

            assert result.valid_rows == 2
            assert result.transactions[0].description == "Restaurant"

        finally:
            Path(temp_path).unlink()

    async def test_parse_csv_missing_required_columns(self, db_session):
        """Test CSV parsing with missing required columns."""
        service = FileImportService(db_session)

        # CSV missing amount column
        csv_content = """Date,Description
01/15/2024,Grocery Store
01/16/2024,Gas Station"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_path = f.name

        try:
            # Should raise ValueError for missing column
            with pytest.raises(ValueError, match="Missing required columns"):
                service.parse_file(temp_path, FileType.CSV)
        finally:
            Path(temp_path).unlink()

    async def test_parse_csv_with_invalid_dates(self, db_session):
        """Test CSV parsing with invalid date formats."""
        service = FileImportService(db_session)

        csv_content = """Date,Description,Amount
01/15/2024,Valid Transaction,-50.00
invalid-date,Invalid Date Transaction,-25.00
01/17/2024,Another Valid,-30.00"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_path = f.name

        try:
            result = service.parse_file(temp_path, FileType.CSV)

            # Should parse valid rows and report errors for invalid ones
            assert result.total_rows == 3
            assert result.valid_rows == 2
            assert len(result.errors) == 1
            assert result.errors[0].row_number == 3  # Row 2 in data (row 3 with header)
            assert "Invalid date format" in result.errors[0].error_message

        finally:
            Path(temp_path).unlink()

    async def test_parse_csv_with_invalid_amounts(self, db_session):
        """Test CSV parsing with invalid amount values."""
        service = FileImportService(db_session)

        csv_content = """Date,Description,Amount
01/15/2024,Valid Transaction,-50.00
01/16/2024,Invalid Amount,not-a-number
01/17/2024,Another Valid,-30.00"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_path = f.name

        try:
            result = service.parse_file(temp_path, FileType.CSV)

            assert result.valid_rows == 2
            assert len(result.errors) == 1
            assert "Invalid amount" in result.errors[0].error_message

        finally:
            Path(temp_path).unlink()

    async def test_parse_csv_with_empty_description(self, db_session):
        """Test CSV parsing with empty description."""
        service = FileImportService(db_session)

        csv_content = """Date,Description,Amount
01/15/2024,Valid Transaction,-50.00
01/16/2024,,-25.00
01/17/2024,Another Valid,-30.00"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_path = f.name

        try:
            result = service.parse_file(temp_path, FileType.CSV)

            assert result.valid_rows == 2
            assert len(result.errors) == 1
            assert "Empty description" in result.errors[0].error_message

        finally:
            Path(temp_path).unlink()

    async def test_parse_csv_with_various_date_formats(self, db_session):
        """Test CSV parsing with different date formats."""
        service = FileImportService(db_session)

        csv_content = """Date,Description,Amount
01/15/2024,MM/DD/YYYY format,-50.00
2024-01-16,YYYY-MM-DD format,-25.00
16/01/2024,DD/MM/YYYY format,-30.00"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_path = f.name

        try:
            result = service.parse_file(temp_path, FileType.CSV)

            # All should parse successfully
            assert result.valid_rows == 3
            assert result.transactions[0].date == datetime(2024, 1, 15)
            assert result.transactions[1].date == datetime(2024, 1, 16)
            # Note: DD/MM/YYYY might be ambiguous, but should parse

        finally:
            Path(temp_path).unlink()

    async def test_parse_csv_with_currency_symbols(self, db_session):
        """Test CSV parsing with currency symbols in amounts."""
        service = FileImportService(db_session)

        csv_content = """Date,Description,Amount
01/15/2024,With Dollar Sign,$50.00
01/16/2024,With Comma,"1,250.00"
01/17/2024,Negative Amount,-$30.50"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_path = f.name

        try:
            result = service.parse_file(temp_path, FileType.CSV)

            assert result.valid_rows == 3
            assert result.transactions[0].amount == Decimal("50.00")
            assert result.transactions[1].amount == Decimal("1250.00")
            assert result.transactions[2].amount == Decimal("30.50")

        finally:
            Path(temp_path).unlink()

    async def test_parse_csv_infer_type_from_amount(self, db_session):
        """Test that transaction type is inferred from amount sign."""
        service = FileImportService(db_session)

        csv_content = """Date,Description,Amount
01/15/2024,Expense Transaction,-50.00
01/16/2024,Income Transaction,1000.00"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_path = f.name

        try:
            result = service.parse_file(temp_path, FileType.CSV)

            assert result.transactions[0].type == "EXPENSE"
            assert result.transactions[1].type == "INCOME"

        finally:
            Path(temp_path).unlink()

    async def test_parse_file_content_csv(self, db_session):
        """Test parsing CSV from file content (bytes)."""
        service = FileImportService(db_session)

        csv_content = b"""Date,Description,Amount
01/15/2024,Grocery Store,-125.50
01/16/2024,Gas Station,-45.00"""

        result = service.parse_file_content(csv_content, FileType.CSV)

        assert result.valid_rows == 2
        assert result.transactions[0].description == "Grocery Store"
        assert result.transactions[1].description == "Gas Station"

    async def test_parse_xlsx_file_success(self, db_session):
        """Test parsing a valid XLSX file."""
        service = FileImportService(db_session)

        # Create DataFrame and save as XLSX
        import pandas as pd

        data = {
            "Date": ["01/15/2024", "01/16/2024"],
            "Description": ["Grocery Store", "Gas Station"],
            "Amount": [-125.50, -45.00],
            "Category": ["Groceries", "Transportation"],
        }
        df = pd.DataFrame(data)

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            df.to_excel(f.name, index=False, engine="openpyxl")
            temp_path = f.name

        try:
            result = service.parse_file(temp_path, FileType.XLSX)

            assert result.valid_rows == 2
            assert result.transactions[0].description == "Grocery Store"
            assert result.transactions[0].amount == Decimal("125.50")

        finally:
            Path(temp_path).unlink()

    async def test_generate_csv_template(self, db_session):
        """Test generating CSV template."""
        service = FileImportService(db_session)

        template_bytes = service.generate_template(FileType.CSV)

        # Verify it's valid CSV
        assert template_bytes is not None
        assert b"date" in template_bytes  # lowercase as per implementation
        assert b"description" in template_bytes
        assert b"amount" in template_bytes
        assert b"category" in template_bytes

        # Parse the template to verify it's valid
        import pandas as pd

        df = pd.read_csv(io.BytesIO(template_bytes))
        assert len(df) == 3  # Should have 3 sample rows
        assert "date" in df.columns
        assert "description" in df.columns
        assert "amount" in df.columns

    async def test_generate_xlsx_template(self, db_session):
        """Test generating XLSX template."""
        service = FileImportService(db_session)

        template_bytes = service.generate_template(FileType.XLSX)

        # Verify it's valid XLSX
        assert template_bytes is not None

        # Parse the template to verify it's valid
        import pandas as pd

        df = pd.read_excel(io.BytesIO(template_bytes))
        assert len(df) == 3  # Should have 3 sample rows
        assert "date" in df.columns
        assert "description" in df.columns
        assert "amount" in df.columns

    async def test_parse_result_success_rate(self, db_session):
        """Test ParseResult success rate calculation."""
        service = FileImportService(db_session)

        csv_content = """Date,Description,Amount
01/15/2024,Valid 1,-50.00
invalid-date,Invalid,-25.00
01/17/2024,Valid 2,-30.00
01/18/2024,Valid 3,-40.00"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_path = f.name

        try:
            result = service.parse_file(temp_path, FileType.CSV)

            assert result.total_rows == 4
            assert result.valid_rows == 3
            assert result.success_rate == 75.0

        finally:
            Path(temp_path).unlink()

    async def test_parse_empty_file(self, db_session):
        """Test parsing an empty CSV file."""
        service = FileImportService(db_session)

        csv_content = """Date,Description,Amount"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_path = f.name

        try:
            result = service.parse_file(temp_path, FileType.CSV)

            assert result.total_rows == 0
            assert result.valid_rows == 0
            assert result.success_rate == 0.0

        finally:
            Path(temp_path).unlink()

    async def test_parse_csv_with_optional_category(self, db_session):
        """Test that category is optional and can be None."""
        service = FileImportService(db_session)

        # CSV without category column
        csv_content = """Date,Description,Amount
01/15/2024,Grocery Store,-125.50
01/16/2024,Gas Station,-45.00"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_path = f.name

        try:
            result = service.parse_file(temp_path, FileType.CSV)

            assert result.valid_rows == 2
            assert result.transactions[0].category is None
            assert result.transactions[1].category is None

        finally:
            Path(temp_path).unlink()

    async def test_parse_csv_case_insensitive_columns(self, db_session):
        """Test that column detection is case-insensitive."""
        service = FileImportService(db_session)

        csv_content = """DATE,DESCRIPTION,AMOUNT
01/15/2024,Grocery Store,-125.50
01/16/2024,Gas Station,-45.00"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_path = f.name

        try:
            result = service.parse_file(temp_path, FileType.CSV)

            assert result.valid_rows == 2
            assert result.transactions[0].description == "Grocery Store"

        finally:
            Path(temp_path).unlink()

    async def test_import_transactions_success(self, db_session, test_user):
        """Test successful transaction import."""
        service = FileImportService(db_session)

        # Create parsed transactions
        parsed_txs = [
            ParsedTransaction(
                date=datetime(2024, 1, 15),
                description="Grocery Store",
                amount=Decimal("125.50"),
                category="Groceries",
                type="EXPENSE",
                row_number=2,
            ),
            ParsedTransaction(
                date=datetime(2024, 1, 16),
                description="Gas Station",
                amount=Decimal("45.00"),
                category="Transportation",
                type="EXPENSE",
                row_number=3,
            ),
        ]

        # Import transactions
        result = await service.import_transactions(
            user_id=test_user.id, parsed_transactions=parsed_txs
        )

        # Verify results
        assert result.total_transactions == 2
        assert result.successful_imports == 2
        assert result.duplicate_count == 0
        assert result.error_count == 0
        assert result.success_rate == 100.0

        # Verify transactions were created
        assert all(tx.status == "SUCCESS" for tx in result.imported)
        assert all(tx.transaction_id is not None for tx in result.imported)

    async def test_import_transactions_with_auto_categorization(self, db_session, test_user):
        """Test import with automatic categorization."""
        service = FileImportService(db_session)

        # Create parsed transaction without category
        parsed_txs = [
            ParsedTransaction(
                date=datetime(2024, 1, 15),
                description="Walmart",
                amount=Decimal("125.50"),
                category=None,  # No category provided
                type="EXPENSE",
                row_number=2,
            )
        ]

        # Import with auto-categorization
        result = await service.import_transactions(
            user_id=test_user.id, parsed_transactions=parsed_txs, auto_categorize=True
        )

        # Should succeed with auto-categorization
        assert result.successful_imports == 1
        assert result.imported[0].status == "SUCCESS"

    async def test_import_transactions_skip_duplicates(self, db_session, test_user):
        """Test that duplicate transactions are skipped."""
        from app.services.transaction_service import TransactionService
        from app.schemas.transaction import TransactionCreate, TransactionType, TransactionSource

        service = FileImportService(db_session)
        tx_service = TransactionService(db_session)

        # Create an existing transaction
        transaction_data = TransactionCreate(
            amount=Decimal("125.50"),
            date=date(2024, 1, 15),
            description="Grocery Store",
            category="Groceries",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL,
        )
        existing_tx = await tx_service.create_transaction(
            user_id=test_user.id, transaction_data=transaction_data
        )
        await db_session.commit()

        # Try to import the same transaction
        parsed_txs = [
            ParsedTransaction(
                date=datetime(2024, 1, 15),
                description="Grocery Store",
                amount=Decimal("125.50"),
                category="Groceries",
                type="EXPENSE",
                row_number=2,
            )
        ]

        result = await service.import_transactions(
            user_id=test_user.id, parsed_transactions=parsed_txs, skip_duplicates=True
        )

        # Should skip duplicate
        assert result.total_transactions == 1
        assert result.successful_imports == 0
        assert result.duplicate_count == 1
        assert result.imported[0].status == "DUPLICATE"

    async def test_import_transactions_allow_duplicates(self, db_session, test_user):
        """Test importing duplicates when skip_duplicates is False."""
        from app.services.transaction_service import TransactionService
        from app.schemas.transaction import TransactionCreate, TransactionType, TransactionSource

        service = FileImportService(db_session)
        tx_service = TransactionService(db_session)

        # Create an existing transaction
        transaction_data = TransactionCreate(
            amount=Decimal("125.50"),
            date=date(2024, 1, 15),
            description="Grocery Store",
            category="Groceries",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL,
        )
        await tx_service.create_transaction(user_id=test_user.id, transaction_data=transaction_data)
        await db_session.commit()

        # Import the same transaction with skip_duplicates=False
        parsed_txs = [
            ParsedTransaction(
                date=datetime(2024, 1, 15),
                description="Grocery Store",
                amount=Decimal("125.50"),
                category="Groceries",
                type="EXPENSE",
                row_number=2,
            )
        ]

        result = await service.import_transactions(
            user_id=test_user.id, parsed_transactions=parsed_txs, skip_duplicates=False
        )

        # Should import duplicate
        assert result.successful_imports == 1
        assert result.duplicate_count == 0

    async def test_import_transactions_mixed_results(self, db_session, test_user):
        """Test import with mix of success, duplicates, and errors."""
        from app.services.transaction_service import TransactionService
        from app.schemas.transaction import TransactionCreate, TransactionType, TransactionSource

        service = FileImportService(db_session)
        tx_service = TransactionService(db_session)

        # Create an existing transaction
        transaction_data = TransactionCreate(
            amount=Decimal("50.00"),
            date=date(2024, 1, 15),
            description="Duplicate Transaction",
            category="Groceries",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL,
        )
        await tx_service.create_transaction(user_id=test_user.id, transaction_data=transaction_data)
        await db_session.commit()

        # Create mixed parsed transactions
        parsed_txs = [
            ParsedTransaction(
                date=datetime(2024, 1, 15),
                description="New Transaction",
                amount=Decimal("100.00"),
                category="Dining",
                type="EXPENSE",
                row_number=2,
            ),
            ParsedTransaction(
                date=datetime(2024, 1, 15),
                description="Duplicate Transaction",
                amount=Decimal("50.00"),
                category="Groceries",
                type="EXPENSE",
                row_number=3,
            ),
            ParsedTransaction(
                date=datetime(2024, 1, 16),
                description="Another New Transaction",
                amount=Decimal("75.00"),
                category="Transportation",
                type="EXPENSE",
                row_number=4,
            ),
        ]

        result = await service.import_transactions(
            user_id=test_user.id, parsed_transactions=parsed_txs, skip_duplicates=True
        )

        # Verify mixed results
        assert result.total_transactions == 3
        assert result.successful_imports == 2
        assert result.duplicate_count == 1
        assert result.success_rate == pytest.approx(66.67, rel=0.1)

    async def test_import_transactions_without_auto_categorization(self, db_session, test_user):
        """Test import without automatic categorization."""
        service = FileImportService(db_session)

        # Create parsed transaction without category
        parsed_txs = [
            ParsedTransaction(
                date=datetime(2024, 1, 15),
                description="Some Store",
                amount=Decimal("125.50"),
                category=None,
                type="EXPENSE",
                row_number=2,
            )
        ]

        # Import without auto-categorization
        result = await service.import_transactions(
            user_id=test_user.id, parsed_transactions=parsed_txs, auto_categorize=False
        )

        # Should succeed with "Uncategorized"
        assert result.successful_imports == 1
        assert result.imported[0].status == "SUCCESS"

    async def test_import_result_success_rate_calculation(self, db_session):
        """Test ImportResult success rate calculation."""
        from app.services.file_import_service import ImportResult

        result = ImportResult(
            imported=[],
            total_transactions=10,
            successful_imports=7,
            duplicate_count=2,
            error_count=1,
        )

        assert result.success_rate == 70.0

    async def test_import_result_success_rate_zero_transactions(self, db_session):
        """Test ImportResult success rate with zero transactions."""
        from app.services.file_import_service import ImportResult

        result = ImportResult(
            imported=[],
            total_transactions=0,
            successful_imports=0,
            duplicate_count=0,
            error_count=0,
        )

        assert result.success_rate == 0.0

    async def test_parse_and_import_workflow(self, db_session, test_user):
        """Test complete parse and import workflow."""
        service = FileImportService(db_session)

        # Create CSV file
        csv_content = """Date,Description,Amount,Category
01/15/2024,Grocery Store,-125.50,Groceries
01/16/2024,Gas Station,-45.00,Transportation
01/17/2024,Restaurant,-67.80,Dining"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_path = f.name

        try:
            # Parse file
            parse_result = service.parse_file(temp_path, FileType.CSV)
            assert parse_result.valid_rows == 3

            # Import parsed transactions
            import_result = await service.import_transactions(
                user_id=test_user.id, parsed_transactions=parse_result.transactions
            )

            # Verify import
            assert import_result.successful_imports == 3
            assert import_result.duplicate_count == 0
            assert import_result.error_count == 0

        finally:
            Path(temp_path).unlink()
