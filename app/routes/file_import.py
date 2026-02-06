"""API routes for file import/export operations."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user_id
from app.services.file_import_service import FileImportService
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["import-export"])


@router.post("/import/transactions")
async def import_transactions(
    user_id: UUID = Depends(get_current_user_id),
    file: UploadFile = File(..., description="CSV or XLSX file to import"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Import transactions from CSV or XLSX file.

    Args:
        user_id: User ID
        file: Uploaded file (CSV or XLSX)
        db: Database session

    Returns:
        Import results with success count and errors
    """
    logger.info(
        "Importing transactions from file",
        user_id=str(user_id),
        filename=file.filename,
        content_type=file.content_type,
    )

    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    file_extension = file.filename.lower().split(".")[-1]
    if file_extension not in ["csv", "xlsx"]:
        raise HTTPException(
            status_code=400, detail="Invalid file format. Only CSV and XLSX files are supported"
        )

    # Read file content
    try:
        content = await file.read()
    except Exception as e:
        logger.error(
            "Failed to read uploaded file",
            user_id=str(user_id),
            filename=file.filename,
            error=str(e),
        )
        raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")

    # Import transactions
    import_service = FileImportService(db)

    try:
        # Step 1: Parse file content
        from app.services.file_import_service import FileType

        file_type = FileType.CSV if file_extension == "csv" else FileType.XLSX
        parse_result = import_service.parse_file_content(file_content=content, file_type=file_type)

        # Check if parsing had errors
        if parse_result.errors:
            logger.warning(
                "File parsing completed with errors",
                user_id=str(user_id),
                filename=file.filename,
                error_count=len(parse_result.errors),
            )

        # Step 2: Import parsed transactions
        import_result = await import_service.import_transactions(
            user_id=user_id,
            parsed_transactions=parse_result.transactions,
            skip_duplicates=True,
            auto_categorize=True,
        )

        # Build response
        result = {
            "success_count": import_result.successful_imports,
            "error_count": import_result.error_count + len(parse_result.errors),
            "duplicate_count": import_result.duplicate_count,
            "imported_transactions": import_result.successful_imports,
            "errors": [
                {
                    "row": error.row_number,
                    "field": error.field,
                    "value": error.value,
                    "message": error.error_message,
                }
                for error in parse_result.errors
            ]
            + [
                {
                    "row": tx.row_number,
                    "field": "transaction",
                    "value": tx.description,
                    "message": tx.error_message or "Import failed",
                }
                for tx in import_result.imported
                if tx.status == "ERROR"
            ],
        }

        logger.info(
            "Transactions imported successfully",
            user_id=str(user_id),
            filename=file.filename,
            success_count=result["success_count"],
            error_count=result["error_count"],
        )

        return result

    except ValueError as e:
        logger.error(
            "Import validation error", user_id=str(user_id), filename=file.filename, error=str(e)
        )
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(
            "Import failed",
            user_id=str(user_id),
            filename=file.filename,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="An internal error occurred. Please try again later.")


@router.get("/export/transactions")
async def export_transactions(
    user_id: UUID = Depends(get_current_user_id),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    category: Optional[str] = Query(None, description="Filter by category"),
    transaction_type: Optional[str] = Query(None, description="Filter by type (INCOME/EXPENSE)"),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Export transactions to CSV file.

    Args:
        user_id: User ID
        start_date: Optional start date filter
        end_date: Optional end date filter
        category: Optional category filter
        transaction_type: Optional type filter
        db: Database session

    Returns:
        CSV file as streaming response
    """
    from datetime import date as date_type

    logger.info(
        "Exporting transactions to CSV",
        user_id=str(user_id),
        start_date=start_date,
        end_date=end_date,
        category=category,
        transaction_type=transaction_type,
    )

    # Parse dates if provided
    start = None
    end = None

    if start_date:
        try:
            start = date_type.fromisoformat(start_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format. Use YYYY-MM-DD")

    if end_date:
        try:
            end = date_type.fromisoformat(end_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_date format. Use YYYY-MM-DD")

    # Validate date range
    if start and end and start > end:
        raise HTTPException(
            status_code=400, detail="Start date must be before or equal to end date"
        )

    # Export transactions
    import_service = FileImportService(db)

    try:
        csv_content = await import_service.export_transactions(
            user_id=user_id,
            start_date=start,
            end_date=end,
            category=category,
            transaction_type=transaction_type,
        )

        # Generate filename
        filename_parts = ["transactions"]
        if start_date:
            filename_parts.append(f"from_{start_date}")
        if end_date:
            filename_parts.append(f"to_{end_date}")
        if category:
            filename_parts.append(f"category_{category}")
        if transaction_type:
            filename_parts.append(f"type_{transaction_type}")

        filename = "_".join(filename_parts) + ".csv"

        logger.info("Transactions exported successfully", user_id=str(user_id), filename=filename)

        return StreamingResponse(
            iter([csv_content]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except Exception as e:
        logger.error("Export failed", user_id=str(user_id), error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred. Please try again later.")


@router.get("/import/template")
async def download_template(
    format: str = Query("csv", description="Template format (csv or xlsx)"),
) -> StreamingResponse:
    """Download a sample import template file.

    Args:
        format: Template format (csv or xlsx)

    Returns:
        Template file as streaming response
    """
    logger.info("Downloading import template", format=format)

    if format not in ["csv", "xlsx"]:
        raise HTTPException(status_code=400, detail="Invalid format. Use 'csv' or 'xlsx'")

    # Generate template
    from app.services.file_import_service import FileType

    import_service = FileImportService(None)  # No DB needed for template

    try:
        file_type = FileType.CSV if format == "csv" else FileType.XLSX
        template_content = import_service.generate_template(file_type=file_type)

        media_type = (
            "text/csv"
            if format == "csv"
            else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        filename = f"transaction_import_template.{format}"

        logger.info("Template generated successfully", format=format, filename=filename)

        return StreamingResponse(
            iter([template_content]),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except Exception as e:
        logger.error("Template generation failed", format=format, error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred. Please try again later.")
