"""Services package."""

# Lazy imports to avoid numpy crash on Python 3.13
# Import services where they're needed instead of here

__all__ = ["TransactionService"]


def __getattr__(name):
    """Lazy import for services that have heavy dependencies."""
    if name == "TransactionService":
        from app.services.transaction_service import TransactionService
        return TransactionService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
