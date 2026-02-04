"""Report service for generating financial reports and analytics."""

from datetime import date as date_type
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID
from dataclasses import dataclass
import csv
import io

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Transaction
from app.models.budget import Budget
from app.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class IncomeSummary:
    """Income summary for a period."""

    total_income: Decimal
    income_by_category: Dict[str, Decimal]
    transaction_count: int


@dataclass
class ExpenseSummary:
    """Expense summary for a period."""

    total_expenses: Decimal
    expenses_by_category: Dict[str, Decimal]
    transaction_count: int
    average_transaction: Decimal


@dataclass
class BudgetAdherence:
    """Budget adherence analysis."""

    budget_id: Optional[UUID]
    budget_name: Optional[str]
    categories: Dict[str, Dict[str, any]]  # category -> {budgeted, actual, variance, adherence_pct}
    overall_adherence: float  # percentage


@dataclass
class SpendingChange:
    """Spending pattern change between periods."""

    category: str
    previous_amount: Decimal
    current_amount: Decimal
    change_amount: Decimal
    change_percent: float
    is_significant: bool  # True if change > 25%


@dataclass
class FinancialReport:
    """Complete financial report for a date range."""

    user_id: UUID
    start_date: date_type
    end_date: date_type
    income_summary: IncomeSummary
    expense_summary: ExpenseSummary
    savings_rate: float  # percentage
    net_savings: Decimal
    budget_adherence: Optional[BudgetAdherence]
    spending_changes: List[SpendingChange]
    generated_at: date_type


class ReportService:
    """Service for generating financial reports and analytics."""

    def __init__(self, db: AsyncSession):
        """Initialize report service.

        Args:
            db: Database session
        """
        self.db = db

    async def generate_report(
        self,
        user_id: UUID,
        start_date: date_type,
        end_date: date_type,
        compare_to_previous_period: bool = True,
    ) -> FinancialReport:
        """Generate a comprehensive financial report for a date range.

        Requirement 11.1: Generate reports for custom date ranges
        Requirement 11.2: Include income summary, expense breakdown, savings rate, budget adherence
        Requirement 11.4: Highlight significant changes in spending patterns

        Args:
            user_id: User ID
            start_date: Report start date
            end_date: Report end date
            compare_to_previous_period: Whether to compare with previous period

        Returns:
            Complete financial report
        """
        logger.info(
            "Generating financial report",
            user_id=str(user_id),
            start_date=str(start_date),
            end_date=str(end_date),
        )

        # Generate income summary
        income_summary = await self._generate_income_summary(user_id, start_date, end_date)

        # Generate expense summary
        expense_summary = await self._generate_expense_summary(user_id, start_date, end_date)

        # Calculate savings rate
        savings_rate, net_savings = self._calculate_savings_rate(
            income_summary.total_income, expense_summary.total_expenses
        )

        # Get budget adherence
        budget_adherence = await self._analyze_budget_adherence(user_id, start_date, end_date)

        # Detect spending pattern changes
        spending_changes = []
        if compare_to_previous_period:
            spending_changes = await self._detect_spending_changes(user_id, start_date, end_date)

        report = FinancialReport(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            income_summary=income_summary,
            expense_summary=expense_summary,
            savings_rate=savings_rate,
            net_savings=net_savings,
            budget_adherence=budget_adherence,
            spending_changes=spending_changes,
            generated_at=date_type.today(),
        )

        logger.info(
            "Financial report generated",
            user_id=str(user_id),
            total_income=str(income_summary.total_income),
            total_expenses=str(expense_summary.total_expenses),
            savings_rate=f"{savings_rate:.2f}%",
        )

        return report

    async def _generate_income_summary(
        self, user_id: UUID, start_date: date_type, end_date: date_type
    ) -> IncomeSummary:
        """Generate income summary for the period."""
        # Get all income transactions
        stmt = (
            select(
                Transaction.category,
                func.sum(Transaction.amount).label("total"),
                func.count(Transaction.id).label("count"),
            )
            .where(
                and_(
                    Transaction.user_id == user_id,
                    Transaction.type == "INCOME",
                    Transaction.date >= start_date,
                    Transaction.date <= end_date,
                    Transaction.deleted_at.is_(None),
                )
            )
            .group_by(Transaction.category)
        )

        result = await self.db.execute(stmt)
        rows = result.all()

        income_by_category = {row.category: Decimal(str(row.total)) for row in rows}

        total_income = sum(income_by_category.values(), Decimal(0))
        transaction_count = sum(row.count for row in rows)

        return IncomeSummary(
            total_income=total_income,
            income_by_category=income_by_category,
            transaction_count=transaction_count,
        )

    async def _generate_expense_summary(
        self, user_id: UUID, start_date: date_type, end_date: date_type
    ) -> ExpenseSummary:
        """Generate expense summary for the period."""
        # Get all expense transactions
        stmt = (
            select(
                Transaction.category,
                func.sum(Transaction.amount).label("total"),
                func.count(Transaction.id).label("count"),
            )
            .where(
                and_(
                    Transaction.user_id == user_id,
                    Transaction.type == "EXPENSE",
                    Transaction.date >= start_date,
                    Transaction.date <= end_date,
                    Transaction.deleted_at.is_(None),
                )
            )
            .group_by(Transaction.category)
        )

        result = await self.db.execute(stmt)
        rows = result.all()

        expenses_by_category = {row.category: Decimal(str(row.total)) for row in rows}

        total_expenses = sum(expenses_by_category.values(), Decimal(0))
        transaction_count = sum(row.count for row in rows)
        average_transaction = (
            total_expenses / transaction_count if transaction_count > 0 else Decimal(0)
        )

        return ExpenseSummary(
            total_expenses=total_expenses,
            expenses_by_category=expenses_by_category,
            transaction_count=transaction_count,
            average_transaction=average_transaction,
        )

    def _calculate_savings_rate(
        self, total_income: Decimal, total_expenses: Decimal
    ) -> tuple[float, Decimal]:
        """Calculate savings rate and net savings.

        Args:
            total_income: Total income for period
            total_expenses: Total expenses for period

        Returns:
            Tuple of (savings_rate percentage, net_savings amount)
        """
        net_savings = total_income - total_expenses

        if total_income > 0:
            savings_rate = float((net_savings / total_income) * 100)
        else:
            savings_rate = 0.0

        return savings_rate, net_savings

    async def _analyze_budget_adherence(
        self, user_id: UUID, start_date: date_type, end_date: date_type
    ) -> Optional[BudgetAdherence]:
        """Analyze budget adherence for the period."""
        # Find budget that covers this period
        stmt = (
            select(Budget)
            .where(
                and_(
                    Budget.user_id == user_id,
                    Budget.period_start <= start_date,
                    Budget.period_end >= end_date,
                )
            )
            .order_by(Budget.created_at.desc())
        )

        result = await self.db.execute(stmt)
        budget = result.scalar_one_or_none()

        if not budget:
            return None

        # Get actual spending by category
        stmt = (
            select(Transaction.category, func.sum(Transaction.amount).label("total"))
            .where(
                and_(
                    Transaction.user_id == user_id,
                    Transaction.type == "EXPENSE",
                    Transaction.date >= start_date,
                    Transaction.date <= end_date,
                    Transaction.deleted_at.is_(None),
                )
            )
            .group_by(Transaction.category)
        )

        result = await self.db.execute(stmt)
        actual_spending = {row.category: Decimal(str(row.total)) for row in result.all()}

        # Calculate adherence for each category
        categories = {}
        total_budgeted = Decimal(0)
        total_actual = Decimal(0)

        for category, budgeted_float in budget.allocations.items():
            budgeted = Decimal(str(budgeted_float))
            actual = actual_spending.get(category, Decimal(0))
            variance = budgeted - actual

            adherence_pct = float((actual / budgeted) * 100) if budgeted > 0 else 0.0

            categories[category] = {
                "budgeted": budgeted,
                "actual": actual,
                "variance": variance,
                "adherence_pct": adherence_pct,
            }

            total_budgeted += budgeted
            total_actual += actual

        # Calculate overall adherence
        overall_adherence = (
            float((total_actual / total_budgeted) * 100) if total_budgeted > 0 else 0.0
        )

        return BudgetAdherence(
            budget_id=budget.id,
            budget_name=budget.name,
            categories=categories,
            overall_adherence=overall_adherence,
        )

    async def _detect_spending_changes(
        self, user_id: UUID, start_date: date_type, end_date: date_type
    ) -> List[SpendingChange]:
        """Detect significant spending pattern changes.

        Requirement 11.4: Highlight significant changes (>25%) in spending patterns

        Args:
            user_id: User ID
            start_date: Current period start date
            end_date: Current period end date

        Returns:
            List of spending changes
        """
        # Calculate period length
        period_days = (end_date - start_date).days + 1

        # Calculate previous period dates
        from datetime import timedelta

        previous_end = start_date - timedelta(days=1)
        previous_start = previous_end - timedelta(days=period_days - 1)

        # Get current period spending
        current_spending = await self._get_spending_by_category(user_id, start_date, end_date)

        # Get previous period spending
        previous_spending = await self._get_spending_by_category(
            user_id, previous_start, previous_end
        )

        # Detect changes
        changes = []
        all_categories = set(current_spending.keys()) | set(previous_spending.keys())

        for category in all_categories:
            current = current_spending.get(category, Decimal(0))
            previous = previous_spending.get(category, Decimal(0))

            # Skip if both are zero
            if current == 0 and previous == 0:
                continue

            change_amount = current - previous

            # Calculate percentage change
            if previous > 0:
                change_percent = float((change_amount / previous) * 100)
            elif current > 0:
                change_percent = 100.0  # New spending category
            else:
                change_percent = 0.0

            # Mark as significant if change > 25%
            is_significant = abs(change_percent) > 25

            changes.append(
                SpendingChange(
                    category=category,
                    previous_amount=previous,
                    current_amount=current,
                    change_amount=change_amount,
                    change_percent=change_percent,
                    is_significant=is_significant,
                )
            )

        # Sort by absolute change amount (largest first)
        changes.sort(key=lambda x: abs(x.change_amount), reverse=True)

        return changes

    async def _get_spending_by_category(
        self, user_id: UUID, start_date: date_type, end_date: date_type
    ) -> Dict[str, Decimal]:
        """Get spending by category for a period."""
        stmt = (
            select(Transaction.category, func.sum(Transaction.amount).label("total"))
            .where(
                and_(
                    Transaction.user_id == user_id,
                    Transaction.type == "EXPENSE",
                    Transaction.date >= start_date,
                    Transaction.date <= end_date,
                    Transaction.deleted_at.is_(None),
                )
            )
            .group_by(Transaction.category)
        )

        result = await self.db.execute(stmt)

        return {row.category: Decimal(str(row.total)) for row in result.all()}

    def export_to_csv(self, report: FinancialReport) -> bytes:
        """Export report to CSV format.

        Requirement 11.3: Provide export options in CSV format

        Args:
            report: Financial report to export

        Returns:
            CSV file content as bytes
        """
        output = io.StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow(["AI-Powered Personal Finance Platform"])
        writer.writerow(["Financial Report"])
        writer.writerow([])

        # Report period
        writer.writerow(["Report Period"])
        writer.writerow(["Start Date", str(report.start_date)])
        writer.writerow(["End Date", str(report.end_date)])
        writer.writerow(["Generated", str(report.generated_at)])
        writer.writerow([])

        # Income summary
        writer.writerow(["Income Summary"])
        writer.writerow(["Total Income", f"${report.income_summary.total_income:.2f}"])
        writer.writerow(["Transaction Count", report.income_summary.transaction_count])
        writer.writerow([])

        if report.income_summary.income_by_category:
            writer.writerow(["Income by Category"])
            writer.writerow(["Category", "Amount"])
            for category, amount in sorted(report.income_summary.income_by_category.items()):
                writer.writerow([category, f"${amount:.2f}"])
            writer.writerow([])

        # Expense summary
        writer.writerow(["Expense Summary"])
        writer.writerow(["Total Expenses", f"${report.expense_summary.total_expenses:.2f}"])
        writer.writerow(["Transaction Count", report.expense_summary.transaction_count])
        writer.writerow(
            ["Average Transaction", f"${report.expense_summary.average_transaction:.2f}"]
        )
        writer.writerow([])

        if report.expense_summary.expenses_by_category:
            writer.writerow(["Expenses by Category"])
            writer.writerow(["Category", "Amount", "Percentage"])
            total = report.expense_summary.total_expenses
            for category, amount in sorted(
                report.expense_summary.expenses_by_category.items(),
                key=lambda x: x[1],
                reverse=True,
            ):
                percentage = float((amount / total) * 100) if total > 0 else 0
                writer.writerow([category, f"${amount:.2f}", f"{percentage:.1f}%"])
            writer.writerow([])

        # Savings
        writer.writerow(["Savings Analysis"])
        writer.writerow(["Net Savings", f"${report.net_savings:.2f}"])
        writer.writerow(["Savings Rate", f"{report.savings_rate:.2f}%"])
        writer.writerow([])

        # Budget adherence
        if report.budget_adherence:
            writer.writerow(["Budget Adherence"])
            writer.writerow(["Budget Name", report.budget_adherence.budget_name])
            writer.writerow(
                ["Overall Adherence", f"{report.budget_adherence.overall_adherence:.1f}%"]
            )
            writer.writerow([])

            writer.writerow(["Budget by Category"])
            writer.writerow(["Category", "Budgeted", "Actual", "Variance", "Adherence %"])
            for category, data in sorted(report.budget_adherence.categories.items()):
                writer.writerow(
                    [
                        category,
                        f"${data['budgeted']:.2f}",
                        f"${data['actual']:.2f}",
                        f"${data['variance']:.2f}",
                        f"{data['adherence_pct']:.1f}%",
                    ]
                )
            writer.writerow([])

        # Spending changes
        if report.spending_changes:
            writer.writerow(["Spending Pattern Changes"])
            writer.writerow(
                ["Category", "Previous", "Current", "Change", "Change %", "Significant"]
            )
            for change in report.spending_changes:
                writer.writerow(
                    [
                        change.category,
                        f"${change.previous_amount:.2f}",
                        f"${change.current_amount:.2f}",
                        f"${change.change_amount:.2f}",
                        f"{change.change_percent:.1f}%",
                        "Yes" if change.is_significant else "No",
                    ]
                )

        # Get CSV content as bytes
        csv_content = output.getvalue()
        output.close()

        logger.info(
            "Report exported to CSV",
            user_id=str(report.user_id),
            start_date=str(report.start_date),
            end_date=str(report.end_date),
        )

        return csv_content.encode("utf-8")

    def export_to_pdf(self, report: FinancialReport) -> bytes:
        """Export report to PDF format.

        Requirement 11.3: Provide export options in PDF format

        Note: This is a simplified PDF export using text-based approach.
        For production, consider using reportlab or weasyprint for better formatting.

        Args:
            report: Financial report to export

        Returns:
            PDF file content as bytes
        """
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib import colors

            # Create PDF in memory
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter)
            styles = getSampleStyleSheet()
            story = []

            # Title
            title_style = ParagraphStyle(
                "CustomTitle",
                parent=styles["Heading1"],
                fontSize=24,
                textColor=colors.HexColor("#1a1a1a"),
                spaceAfter=30,
                alignment=1,  # Center
            )
            story.append(Paragraph("Financial Report", title_style))
            story.append(Spacer(1, 0.2 * inch))

            # Report period
            story.append(
                Paragraph(
                    f"<b>Report Period:</b> {report.start_date} to {report.end_date}",
                    styles["Normal"],
                )
            )
            story.append(Paragraph(f"<b>Generated:</b> {report.generated_at}", styles["Normal"]))
            story.append(Spacer(1, 0.3 * inch))

            # Income Summary
            story.append(Paragraph("<b>Income Summary</b>", styles["Heading2"]))
            income_data = [
                ["Total Income", f"${report.income_summary.total_income:.2f}"],
                ["Transaction Count", str(report.income_summary.transaction_count)],
            ]
            income_table = Table(income_data, colWidths=[3 * inch, 2 * inch])
            income_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f5f5f5")),
                        ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
                        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                        ("FONTSIZE", (0, 0), (-1, -1), 10),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                        ("GRID", (0, 0), (-1, -1), 1, colors.grey),
                    ]
                )
            )
            story.append(income_table)
            story.append(Spacer(1, 0.2 * inch))

            # Income by category
            if report.income_summary.income_by_category:
                story.append(Paragraph("<b>Income by Category</b>", styles["Heading3"]))
                category_data = [["Category", "Amount"]]
                for category, amount in sorted(report.income_summary.income_by_category.items()):
                    category_data.append([category, f"${amount:.2f}"])

                category_table = Table(category_data, colWidths=[3 * inch, 2 * inch])
                category_table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4a90e2")),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                            ("FONTSIZE", (0, 0), (-1, 0), 10),
                            ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                            ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                            ("GRID", (0, 0), (-1, -1), 1, colors.grey),
                        ]
                    )
                )
                story.append(category_table)
                story.append(Spacer(1, 0.3 * inch))

            # Expense Summary
            story.append(Paragraph("<b>Expense Summary</b>", styles["Heading2"]))
            expense_data = [
                ["Total Expenses", f"${report.expense_summary.total_expenses:.2f}"],
                ["Transaction Count", str(report.expense_summary.transaction_count)],
                ["Average Transaction", f"${report.expense_summary.average_transaction:.2f}"],
            ]
            expense_table = Table(expense_data, colWidths=[3 * inch, 2 * inch])
            expense_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f5f5f5")),
                        ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
                        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                        ("FONTSIZE", (0, 0), (-1, -1), 10),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                        ("GRID", (0, 0), (-1, -1), 1, colors.grey),
                    ]
                )
            )
            story.append(expense_table)
            story.append(Spacer(1, 0.2 * inch))

            # Expenses by category
            if report.expense_summary.expenses_by_category:
                story.append(Paragraph("<b>Expenses by Category</b>", styles["Heading3"]))
                expense_category_data = [["Category", "Amount", "Percentage"]]
                total = report.expense_summary.total_expenses
                for category, amount in sorted(
                    report.expense_summary.expenses_by_category.items(),
                    key=lambda x: x[1],
                    reverse=True,
                ):
                    percentage = float((amount / total) * 100) if total > 0 else 0
                    expense_category_data.append([category, f"${amount:.2f}", f"{percentage:.1f}%"])

                expense_category_table = Table(
                    expense_category_data, colWidths=[2.5 * inch, 1.5 * inch, 1 * inch]
                )
                expense_category_table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e74c3c")),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                            ("FONTSIZE", (0, 0), (-1, 0), 10),
                            ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                            ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                            ("GRID", (0, 0), (-1, -1), 1, colors.grey),
                        ]
                    )
                )
                story.append(expense_category_table)
                story.append(Spacer(1, 0.3 * inch))

            # Savings Analysis
            story.append(Paragraph("<b>Savings Analysis</b>", styles["Heading2"]))
            savings_color = (
                colors.HexColor("#27ae60")
                if report.net_savings >= 0
                else colors.HexColor("#e74c3c")
            )
            savings_data = [
                ["Net Savings", f"${report.net_savings:.2f}"],
                ["Savings Rate", f"{report.savings_rate:.2f}%"],
            ]
            savings_table = Table(savings_data, colWidths=[3 * inch, 2 * inch])
            savings_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f5f5f5")),
                        ("TEXTCOLOR", (1, 0), (1, 0), savings_color),
                        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                        ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 10),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                        ("GRID", (0, 0), (-1, -1), 1, colors.grey),
                    ]
                )
            )
            story.append(savings_table)
            story.append(Spacer(1, 0.3 * inch))

            # Budget Adherence
            if report.budget_adherence:
                story.append(Paragraph("<b>Budget Adherence</b>", styles["Heading2"]))
                story.append(
                    Paragraph(f"Budget: {report.budget_adherence.budget_name}", styles["Normal"])
                )
                story.append(
                    Paragraph(
                        f"Overall Adherence: {report.budget_adherence.overall_adherence:.1f}%",
                        styles["Normal"],
                    )
                )
                story.append(Spacer(1, 0.1 * inch))

                budget_data = [["Category", "Budgeted", "Actual", "Variance", "Adherence %"]]
                for category, data in sorted(report.budget_adherence.categories.items()):
                    budget_data.append(
                        [
                            category,
                            f"${data['budgeted']:.2f}",
                            f"${data['actual']:.2f}",
                            f"${data['variance']:.2f}",
                            f"{data['adherence_pct']:.1f}%",
                        ]
                    )

                budget_table = Table(
                    budget_data,
                    colWidths=[1.5 * inch, 1.2 * inch, 1.2 * inch, 1.2 * inch, 1 * inch],
                )
                budget_table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#9b59b6")),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                            ("FONTSIZE", (0, 0), (-1, -1), 8),
                            ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                            ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                            ("GRID", (0, 0), (-1, -1), 1, colors.grey),
                        ]
                    )
                )
                story.append(budget_table)
                story.append(Spacer(1, 0.3 * inch))

            # Spending Changes
            if report.spending_changes:
                story.append(Paragraph("<b>Spending Pattern Changes</b>", styles["Heading2"]))
                changes_data = [["Category", "Previous", "Current", "Change", "Change %"]]
                for change in report.spending_changes[:10]:  # Limit to top 10
                    changes_data.append(
                        [
                            change.category,
                            f"${change.previous_amount:.2f}",
                            f"${change.current_amount:.2f}",
                            f"${change.change_amount:.2f}",
                            f"{change.change_percent:.1f}%",
                        ]
                    )

                changes_table = Table(
                    changes_data,
                    colWidths=[1.5 * inch, 1.2 * inch, 1.2 * inch, 1.2 * inch, 1 * inch],
                )
                changes_table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f39c12")),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                            ("FONTSIZE", (0, 0), (-1, -1), 8),
                            ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                            ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                            ("GRID", (0, 0), (-1, -1), 1, colors.grey),
                        ]
                    )
                )
                story.append(changes_table)

            # Build PDF
            doc.build(story)

            # Get PDF content
            pdf_content = buffer.getvalue()
            buffer.close()

            logger.info(
                "Report exported to PDF",
                user_id=str(report.user_id),
                start_date=str(report.start_date),
                end_date=str(report.end_date),
            )

            return pdf_content

        except ImportError:
            # Fallback if reportlab is not installed
            logger.warning(
                "reportlab not installed, falling back to text-based PDF",
                user_id=str(report.user_id),
            )

            # Create a simple text-based "PDF" (actually just formatted text)
            # In production, reportlab should be installed
            text_content = self._generate_text_report(report)
            return text_content.encode("utf-8")

    def _generate_text_report(self, report: FinancialReport) -> str:
        """Generate a text-based report as fallback.

        Args:
            report: Financial report

        Returns:
            Formatted text report
        """
        lines = []
        lines.append("=" * 80)
        lines.append("FINANCIAL REPORT".center(80))
        lines.append("=" * 80)
        lines.append("")
        lines.append(f"Report Period: {report.start_date} to {report.end_date}")
        lines.append(f"Generated: {report.generated_at}")
        lines.append("")

        # Income Summary
        lines.append("-" * 80)
        lines.append("INCOME SUMMARY")
        lines.append("-" * 80)
        lines.append(f"Total Income: ${report.income_summary.total_income:.2f}")
        lines.append(f"Transaction Count: {report.income_summary.transaction_count}")
        lines.append("")

        if report.income_summary.income_by_category:
            lines.append("Income by Category:")
            for category, amount in sorted(report.income_summary.income_by_category.items()):
                lines.append(f"  {category}: ${amount:.2f}")
            lines.append("")

        # Expense Summary
        lines.append("-" * 80)
        lines.append("EXPENSE SUMMARY")
        lines.append("-" * 80)
        lines.append(f"Total Expenses: ${report.expense_summary.total_expenses:.2f}")
        lines.append(f"Transaction Count: {report.expense_summary.transaction_count}")
        lines.append(f"Average Transaction: ${report.expense_summary.average_transaction:.2f}")
        lines.append("")

        if report.expense_summary.expenses_by_category:
            lines.append("Expenses by Category:")
            total = report.expense_summary.total_expenses
            for category, amount in sorted(
                report.expense_summary.expenses_by_category.items(),
                key=lambda x: x[1],
                reverse=True,
            ):
                percentage = float((amount / total) * 100) if total > 0 else 0
                lines.append(f"  {category}: ${amount:.2f} ({percentage:.1f}%)")
            lines.append("")

        # Savings
        lines.append("-" * 80)
        lines.append("SAVINGS ANALYSIS")
        lines.append("-" * 80)
        lines.append(f"Net Savings: ${report.net_savings:.2f}")
        lines.append(f"Savings Rate: {report.savings_rate:.2f}%")
        lines.append("")

        # Budget Adherence
        if report.budget_adherence:
            lines.append("-" * 80)
            lines.append("BUDGET ADHERENCE")
            lines.append("-" * 80)
            lines.append(f"Budget: {report.budget_adherence.budget_name}")
            lines.append(f"Overall Adherence: {report.budget_adherence.overall_adherence:.1f}%")
            lines.append("")
            lines.append("Budget by Category:")
            for category, data in sorted(report.budget_adherence.categories.items()):
                lines.append(
                    f"  {category}: "
                    f"Budgeted ${data['budgeted']:.2f}, "
                    f"Actual ${data['actual']:.2f}, "
                    f"Variance ${data['variance']:.2f}, "
                    f"Adherence {data['adherence_pct']:.1f}%"
                )
            lines.append("")

        # Spending Changes
        if report.spending_changes:
            lines.append("-" * 80)
            lines.append("SPENDING PATTERN CHANGES")
            lines.append("-" * 80)
            for change in report.spending_changes:
                significant = " (SIGNIFICANT)" if change.is_significant else ""
                lines.append(
                    f"  {change.category}: "
                    f"${change.previous_amount:.2f} → ${change.current_amount:.2f} "
                    f"({change.change_percent:+.1f}%){significant}"
                )
            lines.append("")

        lines.append("=" * 80)

        return "\n".join(lines)
