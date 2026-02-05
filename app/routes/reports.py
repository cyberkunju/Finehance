"""API routes for financial reports."""

from datetime import datetime, timezone
from uuid import uuid4, UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.report_service import ReportService
from app.schemas.report import (
    ReportGenerateRequest,
    FinancialReportResponse,
    IncomeSummaryResponse,
    ExpenseSummaryResponse,
    BudgetAdherenceResponse,
    SpendingChangeResponse,
)
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["reports"])


@router.post("/generate", response_model=FinancialReportResponse)
async def generate_report(
    request: ReportGenerateRequest, db: AsyncSession = Depends(get_db)
) -> FinancialReportResponse:
    """Generate a financial report for a date range.

    Args:
        request: Report generation request
        db: Database session

    Returns:
        Complete financial report
    """
    logger.info(
        "Generating report",
        user_id=str(request.user_id),
        start_date=str(request.start_date),
        end_date=str(request.end_date),
    )

    # Validate date range
    if request.start_date > request.end_date:
        raise HTTPException(
            status_code=400, detail="Start date must be before or equal to end date"
        )

    # Generate report
    report_service = ReportService(db)
    report = await report_service.generate_report(
        user_id=request.user_id,
        start_date=request.start_date,
        end_date=request.end_date,
        compare_to_previous_period=True,
    )

    # Convert to response model
    return FinancialReportResponse(
        report_id=uuid4(),  # Generate unique report ID
        user_id=request.user_id,
        start_date=report.start_date,
        end_date=report.end_date,
        income_summary=IncomeSummaryResponse(
            total_income=report.income_summary.total_income,
            income_by_category=report.income_summary.income_by_category,
            transaction_count=report.income_summary.transaction_count,
        ),
        expense_summary=ExpenseSummaryResponse(
            total_expenses=report.expense_summary.total_expenses,
            expenses_by_category=report.expense_summary.expenses_by_category,
            transaction_count=report.expense_summary.transaction_count,
            average_transaction=report.expense_summary.average_transaction,
        ),
        net_savings=report.net_savings,
        savings_rate=report.savings_rate,
        budget_adherence=(
            BudgetAdherenceResponse(
                budget_id=report.budget_adherence.budget_id,
                budget_name=report.budget_adherence.budget_name,
                categories=report.budget_adherence.categories,
                overall_adherence=report.budget_adherence.overall_adherence,
            )
            if report.budget_adherence
            else None
        ),
        spending_changes=[
            SpendingChangeResponse(
                category=change.category,
                previous_period_avg=change.previous_amount,
                current_period_avg=change.current_amount,
                change_percent=change.change_percent,
                change_direction="increase" if change.change_amount > 0 else "decrease",
            )
            for change in report.spending_changes
        ],
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


@router.post("/export/csv")
async def export_report_csv(
    user_id: UUID = Query(..., description="User ID"),
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    include_budget_analysis: bool = Query(True, description="Include budget analysis"),
    budget_id: Optional[UUID] = Query(None, description="Specific budget ID"),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Export financial report as CSV.

    Args:
        user_id: User ID
        start_date: Report start date
        end_date: Report end date
        include_budget_analysis: Include budget adherence analysis
        budget_id: Specific budget ID for analysis
        db: Database session

    Returns:
        CSV file as streaming response
    """
    from datetime import date as date_type

    # Parse dates
    try:
        start = date_type.fromisoformat(start_date)
        end = date_type.fromisoformat(end_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    # Validate date range
    if start > end:
        raise HTTPException(
            status_code=400, detail="Start date must be before or equal to end date"
        )

    logger.info(
        "Exporting report to CSV", user_id=str(user_id), start_date=start_date, end_date=end_date
    )

    # Generate report
    report_service = ReportService(db)
    report = await report_service.generate_report(
        user_id=user_id, start_date=start, end_date=end, compare_to_previous_period=True
    )

    # Export to CSV
    csv_content = report_service.export_to_csv(report)

    # Return as streaming response
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=financial_report_{start_date}_to_{end_date}.csv"
        },
    )


@router.post("/export/pdf")
async def export_report_pdf(
    user_id: UUID = Query(..., description="User ID"),
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    include_budget_analysis: bool = Query(True, description="Include budget analysis"),
    budget_id: Optional[UUID] = Query(None, description="Specific budget ID"),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Export financial report as PDF.

    Args:
        user_id: User ID
        start_date: Report start date
        end_date: Report end date
        include_budget_analysis: Include budget adherence analysis
        budget_id: Specific budget ID for analysis
        db: Database session

    Returns:
        PDF file as streaming response
    """
    from datetime import date as date_type

    # Parse dates
    try:
        start = date_type.fromisoformat(start_date)
        end = date_type.fromisoformat(end_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    # Validate date range
    if start > end:
        raise HTTPException(
            status_code=400, detail="Start date must be before or equal to end date"
        )

    logger.info(
        "Exporting report to PDF", user_id=str(user_id), start_date=start_date, end_date=end_date
    )

    # Generate report
    report_service = ReportService(db)
    report = await report_service.generate_report(
        user_id=user_id, start_date=start, end_date=end, compare_to_previous_period=True
    )

    # Export to PDF
    pdf_content = report_service.export_to_pdf(report)

    # Return as streaming response
    return StreamingResponse(
        iter([pdf_content]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=financial_report_{start_date}_to_{end_date}.pdf"
        },
    )
