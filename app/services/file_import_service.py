"""File import service for CSV and XLSX transaction files."""

from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Dict, List, Optional
from dataclasses import dataclass
from uuid import UUID
import io

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging_config import get_logger

logger = get_logger(__name__)


class FileType(str, Enum):
    """Supported file types for import."""

    CSV = "CSV"
    XLSX = "XLSX"


@dataclass
class ParsedTransaction:
    """Parsed transaction data from file."""

    date: datetime
    description: str
    amount: Decimal
    category: Optional[str] = None
    type: Optional[str] = None  # INCOME or EXPENSE
    row_number: int = 0


@dataclass
class ParseError:
    """Error encountered during parsing."""

    row_number: int
    field: str
    value: str
    error_message: str


@dataclass
class ParseResult:
    """Result of file parsing operation."""

    transactions: List[ParsedTransaction]
    errors: List[ParseError]
    total_rows: int
    valid_rows: int

    @property
    def success_rate(self) -> float:
        """Calculate success rate of parsing."""
        if self.total_rows == 0:
            return 0.0
        return (self.valid_rows / self.total_rows) * 100


@dataclass
class ImportedTransaction:
    """Result of importing a single transaction."""

    transaction_id: Optional[UUID]
    description: str
    amount: Decimal
    status: str  # SUCCESS, DUPLICATE, ERROR
    error_message: Optional[str] = None
    row_number: int = 0


@dataclass
class ImportResult:
    """Result of transaction import operation."""

    imported: List[ImportedTransaction]
    total_transactions: int
    successful_imports: int
    duplicate_count: int
    error_count: int

    @property
    def success_rate(self) -> float:
        """Calculate success rate of import."""
        if self.total_transactions == 0:
            return 0.0
        return (self.successful_imports / self.total_transactions) * 100


class FileImportService:
    """Service for importing transactions from CSV and XLSX files."""

    # Default column mappings
    DEFAULT_COLUMN_MAPPING = {
        "date": ["date", "transaction_date", "trans_date", "posted_date"],
        "description": ["description", "desc", "merchant", "payee", "memo"],
        "amount": ["amount", "value", "transaction_amount", "trans_amount"],
        "category": ["category", "cat"],
        "type": ["type", "transaction_type", "trans_type", "debit_credit"],
    }

    # Supported date formats
    DATE_FORMATS = [
        "%m/%d/%Y",  # MM/DD/YYYY
        "%d/%m/%Y",  # DD/MM/YYYY
        "%Y-%m-%d",  # YYYY-MM-DD
        "%Y/%m/%d",  # YYYY/MM/DD
        "%m-%d-%Y",  # MM-DD-YYYY
        "%d-%m-%Y",  # DD-MM-YYYY
    ]

    def __init__(self, db: AsyncSession):
        """Initialize file import service.

        Args:
            db: Database session
        """
        self.db = db

    def parse_file(
        self, file_path: str, file_type: FileType, column_mapping: Optional[Dict[str, str]] = None
    ) -> ParseResult:
        """Parse CSV or XLSX file and extract transaction data.

        Args:
            file_path: Path to file to parse
            file_type: Type of file (CSV or XLSX)
            column_mapping: Optional custom column mapping
                           Format: {"date": "Date Column", "description": "Desc", ...}

        Returns:
            ParseResult with parsed transactions and errors
        """
        logger.info("Parsing file", file_path=file_path, file_type=file_type)

        try:
            # Read file into DataFrame
            if file_type == FileType.CSV:
                df = pd.read_csv(file_path)
            elif file_type == FileType.XLSX:
                df = pd.read_excel(file_path)
            else:
                raise ValueError(f"Unsupported file type: {file_type}")

            # Detect column mapping if not provided
            if column_mapping is None:
                column_mapping = self._detect_columns(df)

            # Validate required columns are present
            missing_columns = self._validate_columns(df, column_mapping)
            if missing_columns:
                raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")

            # Parse transactions
            transactions = []
            errors = []

            for idx, row in df.iterrows():
                row_number = idx + 2  # +2 for header row and 0-based index

                try:
                    parsed_tx = self._parse_row(row, column_mapping, row_number)
                    transactions.append(parsed_tx)
                except Exception as e:
                    # Log parsing error but continue
                    logger.warning("Failed to parse row", row_number=row_number, error=str(e))
                    errors.append(
                        ParseError(
                            row_number=row_number,
                            field="row",
                            value=str(row.to_dict()),
                            error_message=str(e),
                        )
                    )

            result = ParseResult(
                transactions=transactions,
                errors=errors,
                total_rows=len(df),
                valid_rows=len(transactions),
            )

            logger.info(
                "File parsing complete",
                total_rows=result.total_rows,
                valid_rows=result.valid_rows,
                error_count=len(errors),
                success_rate=f"{result.success_rate:.1f}%",
            )

            return result

        except Exception as e:
            logger.error("Failed to parse file", file_path=file_path, error=str(e))
            raise

    def parse_file_content(
        self,
        file_content: bytes,
        file_type: FileType,
        column_mapping: Optional[Dict[str, str]] = None,
    ) -> ParseResult:
        """Parse file content (for uploaded files).

        Args:
            file_content: File content as bytes
            file_type: Type of file (CSV or XLSX)
            column_mapping: Optional custom column mapping

        Returns:
            ParseResult with parsed transactions and errors
        """
        try:
            # Read file content into DataFrame
            if file_type == FileType.CSV:
                df = pd.read_csv(io.BytesIO(file_content))
            elif file_type == FileType.XLSX:
                df = pd.read_excel(io.BytesIO(file_content))
            else:
                raise ValueError(f"Unsupported file type: {file_type}")

            # Detect column mapping if not provided
            if column_mapping is None:
                column_mapping = self._detect_columns(df)

            # Validate required columns
            missing_columns = self._validate_columns(df, column_mapping)
            if missing_columns:
                raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")

            # Parse transactions
            transactions = []
            errors = []

            for idx, row in df.iterrows():
                row_number = idx + 2

                try:
                    parsed_tx = self._parse_row(row, column_mapping, row_number)
                    transactions.append(parsed_tx)
                except Exception as e:
                    errors.append(
                        ParseError(
                            row_number=row_number,
                            field="row",
                            value=str(row.to_dict()),
                            error_message=str(e),
                        )
                    )

            return ParseResult(
                transactions=transactions,
                errors=errors,
                total_rows=len(df),
                valid_rows=len(transactions),
            )

        except Exception as e:
            logger.error("Failed to parse file content", error=str(e))
            raise

    def generate_template(self, file_type: FileType) -> bytes:
        """Generate sample template file for download.

        Args:
            file_type: Type of template to generate (CSV or XLSX)

        Returns:
            File content as bytes
        """
        # Create sample data
        sample_data = {
            "date": ["2024-01-15", "2024-01-16", "2024-01-17"],
            "amount": ["100.50", "2500.00", "50.00"],  # Use strings to preserve formatting
            "type": ["EXPENSE", "INCOME", "EXPENSE"],
            "category": ["Groceries", "Salary", "Transportation"],
            "description": ["Weekly shopping", "Monthly salary", "Gas"],
        }

        df = pd.DataFrame(sample_data)

        # Generate file
        buffer = io.BytesIO()

        if file_type == FileType.CSV:
            df.to_csv(buffer, index=False)
        elif file_type == FileType.XLSX:
            df.to_excel(buffer, index=False, engine="openpyxl")
        else:
            raise ValueError(f"Unsupported file type: {file_type}")

        buffer.seek(0)
        return buffer.getvalue()

    def _detect_columns(self, df: pd.DataFrame) -> Dict[str, str]:
        """Detect column mapping from DataFrame columns.

        Args:
            df: DataFrame to analyze

        Returns:
            Dictionary mapping field names to column names
        """
        column_mapping = {}
        df_columns_lower = {col.lower(): col for col in df.columns}

        for field, possible_names in self.DEFAULT_COLUMN_MAPPING.items():
            for name in possible_names:
                if name.lower() in df_columns_lower:
                    column_mapping[field] = df_columns_lower[name.lower()]
                    break

        return column_mapping

    def _validate_columns(self, df: pd.DataFrame, column_mapping: Dict[str, str]) -> List[str]:
        """Validate that required columns are present.

        Args:
            df: DataFrame to validate
            column_mapping: Column mapping to check

        Returns:
            List of missing required column names
        """
        required_fields = ["date", "description", "amount"]
        missing = []

        for field in required_fields:
            if field not in column_mapping:
                missing.append(field)
            elif column_mapping[field] not in df.columns:
                missing.append(field)

        return missing

    def _parse_row(
        self, row: pd.Series, column_mapping: Dict[str, str], row_number: int
    ) -> ParsedTransaction:
        """Parse a single row into a transaction.

        Args:
            row: DataFrame row
            column_mapping: Column mapping
            row_number: Row number for error reporting

        Returns:
            ParsedTransaction object

        Raises:
            ValueError: If row data is invalid
        """
        # Parse date
        date_col = column_mapping["date"]
        date_value = row[date_col]
        parsed_date = self._parse_date(date_value, row_number)

        # Parse description
        desc_col = column_mapping["description"]
        description = str(row[desc_col]).strip()
        if not description or description.lower() == "nan":
            raise ValueError(f"Empty description at row {row_number}")

        # Parse amount
        amount_col = column_mapping["amount"]
        amount = self._parse_amount(row[amount_col], row_number)

        # Parse optional category
        category = None
        if "category" in column_mapping:
            cat_col = column_mapping["category"]
            if cat_col in row.index and pd.notna(row[cat_col]):
                category = str(row[cat_col]).strip()

        # Parse optional type
        tx_type = None
        if "type" in column_mapping:
            type_col = column_mapping["type"]
            if type_col in row.index and pd.notna(row[type_col]):
                tx_type = str(row[type_col]).strip().upper()
                if tx_type not in ["INCOME", "EXPENSE"]:
                    # Invalid type - raise error
                    raise ValueError(
                        f"Invalid transaction type '{tx_type}' at row {row_number}. "
                        f"Must be 'INCOME' or 'EXPENSE'"
                    )

        # Infer type from amount if not provided
        if tx_type is None:
            tx_type = "INCOME" if amount > 0 else "EXPENSE"

        # Ensure amount is positive and adjust based on type
        if tx_type == "EXPENSE" and amount > 0:
            amount = -amount
        elif tx_type == "INCOME" and amount < 0:
            amount = -amount

        return ParsedTransaction(
            date=parsed_date,
            description=description,
            amount=abs(amount),  # Store as positive, type indicates direction
            category=category,
            type=tx_type,
            row_number=row_number,
        )

    def _parse_date(self, date_value: any, row_number: int) -> datetime:
        """Parse date from various formats.

        Args:
            date_value: Date value to parse
            row_number: Row number for error reporting

        Returns:
            Parsed datetime object

        Raises:
            ValueError: If date cannot be parsed
        """
        if pd.isna(date_value):
            raise ValueError(f"Empty date at row {row_number}")

        # If already a datetime, return it
        if isinstance(date_value, datetime):
            return date_value

        # Try to parse as string
        date_str = str(date_value).strip()

        # Try each date format
        for date_format in self.DATE_FORMATS:
            try:
                return datetime.strptime(date_str, date_format)
            except ValueError:
                continue

        # If no format worked, raise error
        raise ValueError(
            f"Invalid date format '{date_str}' at row {row_number}. "
            f"Supported formats: MM/DD/YYYY, DD/MM/YYYY, YYYY-MM-DD"
        )

    def _parse_amount(self, amount_value: any, row_number: int) -> Decimal:
        """Parse amount from various formats.

        Args:
            amount_value: Amount value to parse
            row_number: Row number for error reporting

        Returns:
            Parsed Decimal amount

        Raises:
            ValueError: If amount cannot be parsed
        """
        if pd.isna(amount_value):
            raise ValueError(f"Empty amount at row {row_number}")

        try:
            # Remove currency symbols and commas
            if isinstance(amount_value, str):
                amount_str = amount_value.strip()
                amount_str = amount_str.replace("$", "").replace(",", "").replace("€", "")
                amount_str = amount_str.replace("£", "").replace("¥", "")
                return Decimal(amount_str)
            else:
                return Decimal(str(amount_value))
        except (InvalidOperation, ValueError) as e:
            raise ValueError(f"Invalid amount '{amount_value}' at row {row_number}: {str(e)}")

    async def import_transactions(
        self,
        user_id: UUID,
        parsed_transactions: List[ParsedTransaction],
        skip_duplicates: bool = True,
        auto_categorize: bool = True,
    ) -> "ImportResult":
        """Import parsed transactions into database.

        Args:
            user_id: User ID to import transactions for
            parsed_transactions: List of parsed transactions
            skip_duplicates: Whether to skip duplicate transactions
            auto_categorize: Whether to auto-categorize transactions without category

        Returns:
            ImportResult with import statistics
        """
        from app.services.transaction_service import TransactionService
        from app.ml.categorization_engine import CategorizationEngine
        from app.schemas.transaction import TransactionCreate, TransactionType, TransactionSource

        logger.info(
            "Starting transaction import",
            user_id=str(user_id),
            transaction_count=len(parsed_transactions),
        )

        categorization_engine = CategorizationEngine() if auto_categorize else None
        transaction_service = TransactionService(self.db, categorization_engine)

        imported = []
        successful_imports = 0
        duplicate_count = 0
        error_count = 0

        for parsed_tx in parsed_transactions:
            try:
                # Check for duplicates if enabled
                if skip_duplicates:
                    duplicate = await transaction_service.detect_duplicate(
                        user_id=user_id,
                        amount=parsed_tx.amount,
                        description=parsed_tx.description,
                        date=parsed_tx.date.date(),
                    )

                    if duplicate:
                        imported.append(
                            ImportedTransaction(
                                transaction_id=None,
                                description=parsed_tx.description,
                                amount=parsed_tx.amount,
                                status="DUPLICATE",
                                error_message="Transaction already exists",
                                row_number=parsed_tx.row_number,
                            )
                        )
                        duplicate_count += 1
                        continue

                # Create transaction data schema
                transaction_data = TransactionCreate(
                    amount=parsed_tx.amount,
                    date=parsed_tx.date.date(),
                    description=parsed_tx.description,
                    category=parsed_tx.category
                    or ("Uncategorized" if not auto_categorize else None),
                    type=TransactionType(parsed_tx.type)
                    if parsed_tx.type
                    else TransactionType.EXPENSE,
                    source=TransactionSource.FILE_IMPORT,
                )

                # Create transaction (will auto-categorize if needed)
                transaction = await transaction_service.create_transaction(
                    user_id=user_id,
                    transaction_data=transaction_data,
                    auto_categorize=auto_categorize,
                )

                imported.append(
                    ImportedTransaction(
                        transaction_id=transaction.id,
                        description=parsed_tx.description,
                        amount=parsed_tx.amount,
                        status="SUCCESS",
                        row_number=parsed_tx.row_number,
                    )
                )
                successful_imports += 1

                logger.debug(
                    "Transaction imported",
                    transaction_id=str(transaction.id),
                    description=parsed_tx.description,
                    category=transaction.category,
                )

            except Exception as e:
                logger.error(
                    "Failed to import transaction", description=parsed_tx.description, error=str(e)
                )

                imported.append(
                    ImportedTransaction(
                        transaction_id=None,
                        description=parsed_tx.description,
                        amount=parsed_tx.amount,
                        status="ERROR",
                        error_message=str(e),
                        row_number=parsed_tx.row_number,
                    )
                )
                error_count += 1

        # Commit all changes
        await self.db.commit()

        result = ImportResult(
            imported=imported,
            total_transactions=len(parsed_transactions),
            successful_imports=successful_imports,
            duplicate_count=duplicate_count,
            error_count=error_count,
        )

        logger.info(
            "Transaction import complete",
            total=result.total_transactions,
            successful=result.successful_imports,
            duplicates=result.duplicate_count,
            errors=result.error_count,
            success_rate=f"{result.success_rate:.1f}%",
        )

        return result

    async def export_transactions(
        self,
        user_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        category: Optional[str] = None,
        transaction_type: Optional[str] = None,
    ) -> bytes:
        """Export transactions to CSV format.

        Args:
            user_id: User ID to export transactions for
            start_date: Optional start date filter
            end_date: Optional end date filter
            category: Optional category filter
            transaction_type: Optional transaction type filter (INCOME/EXPENSE)

        Returns:
            CSV content as bytes
        """
        from app.models.transaction import Transaction
        from sqlalchemy import select

        logger.info(
            "Exporting transactions to CSV",
            user_id=str(user_id),
            start_date=start_date,
            end_date=end_date,
            category=category,
            transaction_type=transaction_type,
        )

        # Build query
        query = select(Transaction).where(Transaction.user_id == user_id)

        if start_date:
            query = query.where(Transaction.date >= start_date)

        if end_date:
            query = query.where(Transaction.date <= end_date)

        if category:
            query = query.where(Transaction.category == category)

        if transaction_type:
            query = query.where(Transaction.type == transaction_type)

        # Order by date descending
        query = query.order_by(Transaction.date.desc())

        # Execute query
        result = await self.db.execute(query)
        transactions = result.scalars().all()

        # Convert to DataFrame
        data = {
            "date": [tx.date.isoformat() for tx in transactions],
            "amount": [f"{float(tx.amount):.2f}" for tx in transactions],  # Format with 2 decimals
            "type": [tx.type for tx in transactions],
            "category": [tx.category for tx in transactions],
            "description": [tx.description for tx in transactions],
        }

        df = pd.DataFrame(data)

        # Generate CSV
        buffer = io.BytesIO()
        df.to_csv(buffer, index=False)
        buffer.seek(0)

        logger.info(
            "Transactions exported successfully",
            user_id=str(user_id),
            transaction_count=len(transactions),
        )

        return buffer.getvalue()
