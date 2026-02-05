"""Pydantic schemas for report API endpoints."""

from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional, Any
from uuid import UUID

from pydantic import BaseModel, Field


class ReportGenerateRequest(BaseModel):
    """Request schema for generating a financial report."""

    user_id: UUID = Field(..., description="User ID")
    start_date: date = Field(..., description="Report start date")
    end_date: date = Field(..., description="Report end date")
    include_budget_analysis: bool = Field(
        default=True, description="Include budget adherence analysis"
    )
    budget_id: Optional[UUID] = Field(
        default=None, description="Specific budget ID for analysis (optional)"
    )


class IncomeSummaryResponse(BaseModel):
    """Income summary response."""

    total_income: Decimal
    income_by_category: Dict[str, Decimal]
    transaction_count: int


class ExpenseSummaryResponse(BaseModel):
    """Expense summary response."""

    total_expenses: Decimal
    expenses_by_category: Dict[str, Decimal]
    transaction_count: int
    average_transaction: Decimal


class BudgetAdherenceResponse(BaseModel):
    """Budget adherence analysis response."""

    budget_id: Optional[UUID]
    budget_name: Optional[str]
    categories: Dict[str, Dict[str, Any]]
    overall_adherence: float


class SpendingChangeResponse(BaseModel):
    """Spending pattern change response."""

    category: str
    previous_period_avg: Decimal
    current_period_avg: Decimal
    change_percent: float
    change_direction: str  # "increase" or "decrease"


class FinancialReportResponse(BaseModel):
    """Complete financial report response."""

    report_id: UUID
    user_id: UUID
    start_date: date
    end_date: date
    income_summary: IncomeSummaryResponse
    expense_summary: ExpenseSummaryResponse
    net_savings: Decimal
    savings_rate: float
    budget_adherence: Optional[BudgetAdherenceResponse]
    spending_changes: List[SpendingChangeResponse]
    generated_at: str


class ReportExportRequest(BaseModel):
    """Request schema for exporting a report."""

    format: str = Field(..., description="Export format: 'csv' or 'pdf'", pattern="^(csv|pdf)$")
