"""Tests for report service."""

import pytest
from datetime import date
from decimal import Decimal

from app.services.report_service import ReportService
from app.services.transaction_service import TransactionService
from app.services.budget_service import BudgetService
from app.schemas.transaction import TransactionCreate, TransactionType, TransactionSource


@pytest.mark.asyncio
async def test_generate_report_basic(db_session, test_user):
    """Test basic report generation with income and expenses."""
    report_service = ReportService(db_session)
    transaction_service = TransactionService(db_session)

    # Create test transactions
    start_date = date(2024, 1, 1)
    end_date = date(2024, 1, 31)

    # Income transactions
    await transaction_service.create_transaction(
        user_id=test_user.id,
        transaction_data=TransactionCreate(
            amount=Decimal("5000.00"),
            date=date(2024, 1, 15),
            description="Salary",
            category="Salary",
            type=TransactionType.INCOME,
            source=TransactionSource.MANUAL,
        ),
    )

    # Expense transactions
    await transaction_service.create_transaction(
        user_id=test_user.id,
        transaction_data=TransactionCreate(
            amount=Decimal("1200.00"),
            date=date(2024, 1, 5),
            description="Rent payment",
            category="Housing",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL,
        ),
    )

    await transaction_service.create_transaction(
        user_id=test_user.id,
        transaction_data=TransactionCreate(
            amount=Decimal("300.00"),
            date=date(2024, 1, 10),
            description="Grocery shopping",
            category="Groceries",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL,
        ),
    )

    await db_session.commit()

    # Generate report
    report = await report_service.generate_report(
        user_id=test_user.id,
        start_date=start_date,
        end_date=end_date,
        compare_to_previous_period=False,
    )

    # Verify report structure
    assert report.user_id == test_user.id
    assert report.start_date == start_date
    assert report.end_date == end_date

    # Verify income summary
    assert report.income_summary.total_income == Decimal("5000.00")
    assert report.income_summary.income_by_category["Salary"] == Decimal("5000.00")
    assert report.income_summary.transaction_count == 1

    # Verify expense summary
    assert report.expense_summary.total_expenses == Decimal("1500.00")
    assert report.expense_summary.expenses_by_category["Housing"] == Decimal("1200.00")
    assert report.expense_summary.expenses_by_category["Groceries"] == Decimal("300.00")
    assert report.expense_summary.transaction_count == 2

    # Verify savings rate
    assert report.savings_rate == 70.0  # (5000 - 1500) / 5000 * 100
    assert report.net_savings == Decimal("3500.00")


@pytest.mark.asyncio
async def test_generate_report_with_budget_adherence(db_session, test_user):
    """Test report generation with budget adherence analysis."""
    report_service = ReportService(db_session)
    transaction_service = TransactionService(db_session)
    budget_service = BudgetService(db_session)

    start_date = date(2024, 2, 1)
    end_date = date(2024, 2, 29)

    # Create budget
    budget = await budget_service.create_budget(
        user_id=test_user.id,
        name="February Budget",
        period_start=start_date,
        period_end=end_date,
        allocations={
            "Groceries": Decimal("400.00"),
            "Dining": Decimal("200.00"),
            "Transportation": Decimal("150.00"),
        },
    )

    # Create expense transactions
    await transaction_service.create_transaction(
        user_id=test_user.id,
        transaction_data=TransactionCreate(
            amount=Decimal("350.00"),
            date=date(2024, 2, 10),
            description="Grocery shopping",
            category="Groceries",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL,
        ),
    )

    await transaction_service.create_transaction(
        user_id=test_user.id,
        transaction_data=TransactionCreate(
            amount=Decimal("250.00"),
            date=date(2024, 2, 15),
            description="Restaurant",
            category="Dining",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL,
        ),
    )

    await db_session.commit()

    # Generate report
    report = await report_service.generate_report(
        user_id=test_user.id,
        start_date=start_date,
        end_date=end_date,
        compare_to_previous_period=False,
    )

    # Verify budget adherence
    assert report.budget_adherence is not None
    assert report.budget_adherence.budget_id == budget.id
    assert report.budget_adherence.budget_name == "February Budget"

    # Check Groceries adherence (350/400 = 87.5%)
    groceries = report.budget_adherence.categories["Groceries"]
    assert groceries["budgeted"] == Decimal("400.00")
    assert groceries["actual"] == Decimal("350.00")
    assert groceries["variance"] == Decimal("50.00")
    assert groceries["adherence_pct"] == 87.5

    # Check Dining adherence (250/200 = 125% - over budget)
    dining = report.budget_adherence.categories["Dining"]
    assert dining["budgeted"] == Decimal("200.00")
    assert dining["actual"] == Decimal("250.00")
    assert dining["variance"] == Decimal("-50.00")
    assert dining["adherence_pct"] == 125.0

    # Check Transportation adherence (0/150 = 0%)
    transportation = report.budget_adherence.categories["Transportation"]
    assert transportation["budgeted"] == Decimal("150.00")
    assert transportation["actual"] == Decimal("0.00")
    assert transportation["adherence_pct"] == 0.0


@pytest.mark.asyncio
async def test_generate_report_spending_changes(db_session, test_user):
    """Test detection of spending pattern changes between periods."""
    report_service = ReportService(db_session)
    transaction_service = TransactionService(db_session)

    # Previous period (January)
    await transaction_service.create_transaction(
        user_id=test_user.id,
        transaction_data=TransactionCreate(
            amount=Decimal("400.00"),
            date=date(2024, 1, 15),
            description="Grocery shopping",
            category="Groceries",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL,
        ),
    )

    await transaction_service.create_transaction(
        user_id=test_user.id,
        transaction_data=TransactionCreate(
            amount=Decimal("100.00"),
            date=date(2024, 1, 20),
            description="Restaurant",
            category="Dining",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL,
        ),
    )

    # Current period (February) - significant changes
    await transaction_service.create_transaction(
        user_id=test_user.id,
        transaction_data=TransactionCreate(
            amount=Decimal("600.00"),  # 50% increase
            date=date(2024, 2, 15),
            description="Grocery shopping",
            category="Groceries",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL,
        ),
    )

    await transaction_service.create_transaction(
        user_id=test_user.id,
        transaction_data=TransactionCreate(
            amount=Decimal("50.00"),  # 50% decrease
            date=date(2024, 2, 20),
            description="Restaurant",
            category="Dining",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL,
        ),
    )

    await db_session.commit()

    # Generate report for February with comparison
    report = await report_service.generate_report(
        user_id=test_user.id,
        start_date=date(2024, 2, 1),
        end_date=date(2024, 2, 29),
        compare_to_previous_period=True,
    )

    # Verify spending changes detected
    assert len(report.spending_changes) > 0

    # Find Groceries change
    groceries_change = next((c for c in report.spending_changes if c.category == "Groceries"), None)
    assert groceries_change is not None
    assert groceries_change.previous_amount == Decimal("400.00")
    assert groceries_change.current_amount == Decimal("600.00")
    assert groceries_change.change_amount == Decimal("200.00")
    assert groceries_change.change_percent == 50.0
    assert groceries_change.is_significant is True  # >25% change

    # Find Dining change
    dining_change = next((c for c in report.spending_changes if c.category == "Dining"), None)
    assert dining_change is not None
    assert dining_change.previous_amount == Decimal("100.00")
    assert dining_change.current_amount == Decimal("50.00")
    assert dining_change.change_amount == Decimal("-50.00")
    assert dining_change.change_percent == -50.0
    assert dining_change.is_significant is True  # >25% change


@pytest.mark.asyncio
async def test_generate_report_empty_period(db_session, test_user):
    """Test report generation for period with no transactions."""
    report_service = ReportService(db_session)

    # Generate report for empty period
    report = await report_service.generate_report(
        user_id=test_user.id,
        start_date=date(2024, 3, 1),
        end_date=date(2024, 3, 31),
        compare_to_previous_period=False,
    )

    # Verify empty report
    assert report.income_summary.total_income == Decimal("0.00")
    assert report.income_summary.transaction_count == 0
    assert report.expense_summary.total_expenses == Decimal("0.00")
    assert report.expense_summary.transaction_count == 0
    assert report.savings_rate == 0.0
    assert report.net_savings == Decimal("0.00")
    assert report.budget_adherence is None


@pytest.mark.asyncio
async def test_generate_report_date_range_filtering(db_session, test_user):
    """Test that report only includes transactions within date range."""
    report_service = ReportService(db_session)
    transaction_service = TransactionService(db_session)

    # Create transactions in different months
    await transaction_service.create_transaction(
        user_id=test_user.id,
        transaction_data=TransactionCreate(
            amount=Decimal("1000.00"),
            date=date(2024, 1, 15),
            description="January income",
            category="Salary",
            type=TransactionType.INCOME,
            source=TransactionSource.MANUAL,
        ),
    )

    await transaction_service.create_transaction(
        user_id=test_user.id,
        transaction_data=TransactionCreate(
            amount=Decimal("2000.00"),
            date=date(2024, 2, 15),
            description="February income",
            category="Salary",
            type=TransactionType.INCOME,
            source=TransactionSource.MANUAL,
        ),
    )

    await transaction_service.create_transaction(
        user_id=test_user.id,
        transaction_data=TransactionCreate(
            amount=Decimal("3000.00"),
            date=date(2024, 3, 15),
            description="March income",
            category="Salary",
            type=TransactionType.INCOME,
            source=TransactionSource.MANUAL,
        ),
    )

    await db_session.commit()

    # Generate report for February only
    report = await report_service.generate_report(
        user_id=test_user.id,
        start_date=date(2024, 2, 1),
        end_date=date(2024, 2, 29),
        compare_to_previous_period=False,
    )

    # Verify only February transaction included
    assert report.income_summary.total_income == Decimal("2000.00")
    assert report.income_summary.transaction_count == 1


@pytest.mark.asyncio
async def test_generate_report_multiple_categories(db_session, test_user):
    """Test report with multiple expense categories."""
    report_service = ReportService(db_session)
    transaction_service = TransactionService(db_session)

    start_date = date(2024, 4, 1)
    end_date = date(2024, 4, 30)

    # Create diverse expenses
    categories_amounts = {
        "Groceries": Decimal("450.00"),
        "Dining": Decimal("200.00"),
        "Transportation": Decimal("150.00"),
        "Entertainment": Decimal("100.00"),
        "Utilities": Decimal("180.00"),
    }

    for category, amount in categories_amounts.items():
        await transaction_service.create_transaction(
            user_id=test_user.id,
            transaction_data=TransactionCreate(
                amount=amount,
                date=date(2024, 4, 15),
                description=f"{category} expense",
                category=category,
                type=TransactionType.EXPENSE,
                source=TransactionSource.MANUAL,
            ),
        )

    await db_session.commit()

    # Generate report
    report = await report_service.generate_report(
        user_id=test_user.id,
        start_date=start_date,
        end_date=end_date,
        compare_to_previous_period=False,
    )

    # Verify all categories present
    assert len(report.expense_summary.expenses_by_category) == 5
    for category, amount in categories_amounts.items():
        assert report.expense_summary.expenses_by_category[category] == amount

    # Verify total
    expected_total = sum(categories_amounts.values())
    assert report.expense_summary.total_expenses == expected_total


@pytest.mark.asyncio
async def test_generate_report_savings_rate_calculation(db_session, test_user):
    """Test savings rate calculation with various scenarios."""
    report_service = ReportService(db_session)
    transaction_service = TransactionService(db_session)

    start_date = date(2024, 5, 1)
    end_date = date(2024, 5, 31)

    # Scenario: 30% savings rate
    await transaction_service.create_transaction(
        user_id=test_user.id,
        transaction_data=TransactionCreate(
            amount=Decimal("5000.00"),
            date=date(2024, 5, 1),
            description="Income",
            category="Salary",
            type=TransactionType.INCOME,
            source=TransactionSource.MANUAL,
        ),
    )

    await transaction_service.create_transaction(
        user_id=test_user.id,
        transaction_data=TransactionCreate(
            amount=Decimal("3500.00"),
            date=date(2024, 5, 15),
            description="Expenses",
            category="Various",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL,
        ),
    )

    await db_session.commit()

    # Generate report
    report = await report_service.generate_report(
        user_id=test_user.id,
        start_date=start_date,
        end_date=end_date,
        compare_to_previous_period=False,
    )

    # Verify savings rate
    assert report.savings_rate == 30.0  # (5000 - 3500) / 5000 * 100
    assert report.net_savings == Decimal("1500.00")


@pytest.mark.asyncio
async def test_generate_report_negative_savings(db_session, test_user):
    """Test report when expenses exceed income (negative savings)."""
    report_service = ReportService(db_session)
    transaction_service = TransactionService(db_session)

    start_date = date(2024, 6, 1)
    end_date = date(2024, 6, 30)

    # Expenses exceed income
    await transaction_service.create_transaction(
        user_id=test_user.id,
        transaction_data=TransactionCreate(
            amount=Decimal("3000.00"),
            date=date(2024, 6, 1),
            description="Income",
            category="Salary",
            type=TransactionType.INCOME,
            source=TransactionSource.MANUAL,
        ),
    )

    await transaction_service.create_transaction(
        user_id=test_user.id,
        transaction_data=TransactionCreate(
            amount=Decimal("4000.00"),
            date=date(2024, 6, 15),
            description="Expenses",
            category="Various",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL,
        ),
    )

    await db_session.commit()

    # Generate report
    report = await report_service.generate_report(
        user_id=test_user.id,
        start_date=start_date,
        end_date=end_date,
        compare_to_previous_period=False,
    )

    # Verify negative savings (use approximate comparison for floating point)
    assert abs(report.savings_rate - (-33.33333333333333)) < 0.0001  # (3000 - 4000) / 3000 * 100
    assert report.net_savings == Decimal("-1000.00")


@pytest.mark.asyncio
async def test_generate_report_no_budget(db_session, test_user):
    """Test report generation when no budget exists for period."""
    report_service = ReportService(db_session)
    transaction_service = TransactionService(db_session)

    start_date = date(2024, 7, 1)
    end_date = date(2024, 7, 31)

    # Create transaction without budget
    await transaction_service.create_transaction(
        user_id=test_user.id,
        transaction_data=TransactionCreate(
            amount=Decimal("500.00"),
            date=date(2024, 7, 15),
            description="Expense",
            category="Shopping",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL,
        ),
    )

    await db_session.commit()

    # Generate report
    report = await report_service.generate_report(
        user_id=test_user.id,
        start_date=start_date,
        end_date=end_date,
        compare_to_previous_period=False,
    )

    # Verify no budget adherence
    assert report.budget_adherence is None


@pytest.mark.asyncio
async def test_generate_report_average_transaction(db_session, test_user):
    """Test average transaction calculation."""
    report_service = ReportService(db_session)
    transaction_service = TransactionService(db_session)

    start_date = date(2024, 8, 1)
    end_date = date(2024, 8, 31)

    # Create multiple transactions
    amounts = [Decimal("100.00"), Decimal("200.00"), Decimal("300.00")]
    for amount in amounts:
        await transaction_service.create_transaction(
            user_id=test_user.id,
            transaction_data=TransactionCreate(
                amount=amount,
                date=date(2024, 8, 15),
                description="Expense",
                category="Various",
                type=TransactionType.EXPENSE,
                source=TransactionSource.MANUAL,
            ),
        )

    await db_session.commit()

    # Generate report
    report = await report_service.generate_report(
        user_id=test_user.id,
        start_date=start_date,
        end_date=end_date,
        compare_to_previous_period=False,
    )

    # Verify average
    expected_average = sum(amounts) / len(amounts)
    assert report.expense_summary.average_transaction == expected_average
    assert report.expense_summary.transaction_count == 3


@pytest.mark.asyncio
async def test_export_to_csv_basic(db_session, test_user):
    """Test basic CSV export functionality."""
    report_service = ReportService(db_session)
    transaction_service = TransactionService(db_session)

    start_date = date(2024, 9, 1)
    end_date = date(2024, 9, 30)

    # Create test data
    await transaction_service.create_transaction(
        user_id=test_user.id,
        transaction_data=TransactionCreate(
            amount=Decimal("3000.00"),
            date=date(2024, 9, 1),
            description="Salary",
            category="Salary",
            type=TransactionType.INCOME,
            source=TransactionSource.MANUAL,
        ),
    )

    await transaction_service.create_transaction(
        user_id=test_user.id,
        transaction_data=TransactionCreate(
            amount=Decimal("500.00"),
            date=date(2024, 9, 15),
            description="Groceries",
            category="Groceries",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL,
        ),
    )

    await db_session.commit()

    # Generate report
    report = await report_service.generate_report(
        user_id=test_user.id,
        start_date=start_date,
        end_date=end_date,
        compare_to_previous_period=False,
    )

    # Export to CSV
    csv_bytes = report_service.export_to_csv(report)

    # Verify CSV content
    assert isinstance(csv_bytes, bytes)
    csv_content = csv_bytes.decode("utf-8")

    # Check for key sections
    assert "Financial Report" in csv_content
    assert "Income Summary" in csv_content
    assert "Expense Summary" in csv_content
    assert "Savings Analysis" in csv_content
    assert "$3000.00" in csv_content  # Income
    assert "$500.00" in csv_content  # Expense
    assert "Salary" in csv_content
    assert "Groceries" in csv_content


@pytest.mark.asyncio
async def test_export_to_csv_with_budget(db_session, test_user):
    """Test CSV export with budget adherence section."""
    report_service = ReportService(db_session)
    transaction_service = TransactionService(db_session)
    budget_service = BudgetService(db_session)

    start_date = date(2024, 10, 1)
    end_date = date(2024, 10, 31)

    # Create budget
    await budget_service.create_budget(
        user_id=test_user.id,
        name="October Budget",
        period_start=start_date,
        period_end=end_date,
        allocations={"Groceries": Decimal("600.00"), "Dining": Decimal("300.00")},
    )

    # Create transactions
    await transaction_service.create_transaction(
        user_id=test_user.id,
        transaction_data=TransactionCreate(
            amount=Decimal("450.00"),
            date=date(2024, 10, 15),
            description="Groceries",
            category="Groceries",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL,
        ),
    )

    await db_session.commit()

    # Generate report
    report = await report_service.generate_report(
        user_id=test_user.id,
        start_date=start_date,
        end_date=end_date,
        compare_to_previous_period=False,
    )

    # Export to CSV
    csv_bytes = report_service.export_to_csv(report)
    csv_content = csv_bytes.decode("utf-8")

    # Verify budget section present
    assert "Budget Adherence" in csv_content
    assert "October Budget" in csv_content
    assert "Budget by Category" in csv_content
    assert "Budgeted" in csv_content
    assert "Actual" in csv_content
    assert "Variance" in csv_content


@pytest.mark.asyncio
async def test_export_to_csv_with_spending_changes(db_session, test_user):
    """Test CSV export with spending pattern changes."""
    report_service = ReportService(db_session)
    transaction_service = TransactionService(db_session)

    # Previous period
    await transaction_service.create_transaction(
        user_id=test_user.id,
        transaction_data=TransactionCreate(
            amount=Decimal("200.00"),
            date=date(2024, 10, 15),
            description="Groceries",
            category="Groceries",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL,
        ),
    )

    # Current period with significant change
    await transaction_service.create_transaction(
        user_id=test_user.id,
        transaction_data=TransactionCreate(
            amount=Decimal("400.00"),
            date=date(2024, 11, 15),
            description="Groceries",
            category="Groceries",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL,
        ),
    )

    await db_session.commit()

    # Generate report with comparison
    report = await report_service.generate_report(
        user_id=test_user.id,
        start_date=date(2024, 11, 1),
        end_date=date(2024, 11, 30),
        compare_to_previous_period=True,
    )

    # Export to CSV
    csv_bytes = report_service.export_to_csv(report)
    csv_content = csv_bytes.decode("utf-8")

    # Verify spending changes section
    assert "Spending Pattern Changes" in csv_content
    assert "Previous" in csv_content
    assert "Current" in csv_content
    assert "Change" in csv_content
    assert "Significant" in csv_content


@pytest.mark.asyncio
async def test_export_to_pdf_basic(db_session, test_user):
    """Test basic PDF export functionality."""
    report_service = ReportService(db_session)
    transaction_service = TransactionService(db_session)

    start_date = date(2024, 12, 1)
    end_date = date(2024, 12, 31)

    # Create test data
    await transaction_service.create_transaction(
        user_id=test_user.id,
        transaction_data=TransactionCreate(
            amount=Decimal("4000.00"),
            date=date(2024, 12, 1),
            description="Salary",
            category="Salary",
            type=TransactionType.INCOME,
            source=TransactionSource.MANUAL,
        ),
    )

    await transaction_service.create_transaction(
        user_id=test_user.id,
        transaction_data=TransactionCreate(
            amount=Decimal("800.00"),
            date=date(2024, 12, 15),
            description="Rent",
            category="Housing",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL,
        ),
    )

    await db_session.commit()

    # Generate report
    report = await report_service.generate_report(
        user_id=test_user.id,
        start_date=start_date,
        end_date=end_date,
        compare_to_previous_period=False,
    )

    # Export to PDF
    pdf_bytes = report_service.export_to_pdf(report)

    # Verify PDF content
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0

    # PDF files start with %PDF
    assert pdf_bytes[:4] == b"%PDF"


@pytest.mark.asyncio
async def test_export_to_pdf_with_all_sections(db_session, test_user):
    """Test PDF export with all sections (income, expenses, budget, spending changes)."""
    report_service = ReportService(db_session)
    transaction_service = TransactionService(db_session)
    budget_service = BudgetService(db_session)

    # Previous period transactions
    await transaction_service.create_transaction(
        user_id=test_user.id,
        transaction_data=TransactionCreate(
            amount=Decimal("300.00"),
            date=date(2024, 11, 15),
            description="Groceries",
            category="Groceries",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL,
        ),
    )

    # Current period
    start_date = date(2024, 12, 1)
    end_date = date(2024, 12, 31)

    # Create budget
    await budget_service.create_budget(
        user_id=test_user.id,
        name="December Budget",
        period_start=start_date,
        period_end=end_date,
        allocations={"Groceries": Decimal("500.00"), "Dining": Decimal("200.00")},
    )

    # Create income
    await transaction_service.create_transaction(
        user_id=test_user.id,
        transaction_data=TransactionCreate(
            amount=Decimal("5000.00"),
            date=date(2024, 12, 1),
            description="Salary",
            category="Salary",
            type=TransactionType.INCOME,
            source=TransactionSource.MANUAL,
        ),
    )

    # Create expenses with significant change
    await transaction_service.create_transaction(
        user_id=test_user.id,
        transaction_data=TransactionCreate(
            amount=Decimal("450.00"),
            date=date(2024, 12, 10),
            description="Groceries",
            category="Groceries",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL,
        ),
    )

    await transaction_service.create_transaction(
        user_id=test_user.id,
        transaction_data=TransactionCreate(
            amount=Decimal("150.00"),
            date=date(2024, 12, 20),
            description="Restaurant",
            category="Dining",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL,
        ),
    )

    await db_session.commit()

    # Generate report with all features
    report = await report_service.generate_report(
        user_id=test_user.id,
        start_date=start_date,
        end_date=end_date,
        compare_to_previous_period=True,
    )

    # Export to PDF
    pdf_bytes = report_service.export_to_pdf(report)

    # Verify PDF was generated
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0
    assert pdf_bytes[:4] == b"%PDF"

    # Verify report has all sections
    assert report.income_summary.total_income > 0
    assert report.expense_summary.total_expenses > 0
    assert report.budget_adherence is not None
    assert len(report.spending_changes) > 0


@pytest.mark.asyncio
async def test_csv_content_validation(db_session, test_user):
    """Test CSV content structure and data accuracy."""
    report_service = ReportService(db_session)
    transaction_service = TransactionService(db_session)

    start_date = date(2025, 1, 1)
    end_date = date(2025, 1, 31)

    # Create specific test data
    await transaction_service.create_transaction(
        user_id=test_user.id,
        transaction_data=TransactionCreate(
            amount=Decimal("2500.00"),
            date=date(2025, 1, 15),
            description="Salary",
            category="Salary",
            type=TransactionType.INCOME,
            source=TransactionSource.MANUAL,
        ),
    )

    await transaction_service.create_transaction(
        user_id=test_user.id,
        transaction_data=TransactionCreate(
            amount=Decimal("1000.00"),
            date=date(2025, 1, 20),
            description="Rent",
            category="Housing",
            type=TransactionType.EXPENSE,
            source=TransactionSource.MANUAL,
        ),
    )

    await db_session.commit()

    # Generate report
    report = await report_service.generate_report(
        user_id=test_user.id,
        start_date=start_date,
        end_date=end_date,
        compare_to_previous_period=False,
    )

    # Export to CSV
    csv_bytes = report_service.export_to_csv(report)
    csv_content = csv_bytes.decode("utf-8")

    # Parse CSV to verify structure
    import csv
    import io

    csv_reader = csv.reader(io.StringIO(csv_content))
    rows = list(csv_reader)

    # Verify CSV has content
    assert len(rows) > 10

    # Verify specific values are present
    csv_text = csv_content
    assert "2500.00" in csv_text  # Income amount
    assert "1000.00" in csv_text  # Expense amount
    assert "60.00%" in csv_text  # Savings rate (1500/2500 * 100)
    assert "1500.00" in csv_text  # Net savings


@pytest.mark.asyncio
async def test_pdf_generation_success(db_session, test_user):
    """Test that PDF generation completes without errors."""
    report_service = ReportService(db_session)
    transaction_service = TransactionService(db_session)

    start_date = date(2025, 2, 1)
    end_date = date(2025, 2, 28)

    # Create minimal test data
    await transaction_service.create_transaction(
        user_id=test_user.id,
        transaction_data=TransactionCreate(
            amount=Decimal("1000.00"),
            date=date(2025, 2, 15),
            description="Income",
            category="Other",
            type=TransactionType.INCOME,
            source=TransactionSource.MANUAL,
        ),
    )

    await db_session.commit()

    # Generate report
    report = await report_service.generate_report(
        user_id=test_user.id,
        start_date=start_date,
        end_date=end_date,
        compare_to_previous_period=False,
    )

    # Export to PDF should not raise any exceptions
    try:
        pdf_bytes = report_service.export_to_pdf(report)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0
    except Exception as e:
        pytest.fail(f"PDF generation failed with exception: {e}")
