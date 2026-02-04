"""
Inference package for AI Brain.

Provides:
- FinancialBrain: Main inference engine (requires torch)
- ConfidenceCalculator: Token probability-based confidence scoring
- ResponseValidator: Hallucination detection and fact-checking
"""

# Brain service requires torch - only import if available
try:
    from .brain_service import FinancialBrain, BrainMode, BrainResponse

    BRAIN_AVAILABLE = True
except ImportError:
    BRAIN_AVAILABLE = False
    FinancialBrain = None
    BrainMode = None
    BrainResponse = None

# These modules work without torch
try:
    from .confidence import ConfidenceCalculator, ConfidenceResult, ConfidenceLevel, TORCH_AVAILABLE
except ImportError:
    ConfidenceCalculator = None
    ConfidenceResult = None
    ConfidenceLevel = None
    TORCH_AVAILABLE = False

try:
    from .validation import (
        ResponseValidator,
        ValidationResult,
        ValidationIssue,
        ValidationSeverity,
        HallucinationDetector,
        FinancialFactChecker,
        CategoryValidator,
    )
except ImportError:
    ResponseValidator = None
    ValidationResult = None
    ValidationIssue = None
    ValidationSeverity = None
    HallucinationDetector = None
    FinancialFactChecker = None
    CategoryValidator = None

try:
    from .templates import ResponseFormatter, format_response, DisclaimerGenerator
except ImportError:
    ResponseFormatter = None
    format_response = None
    DisclaimerGenerator = None

__all__ = [
    "FinancialBrain",
    "BrainMode",
    "BrainResponse",
    "BRAIN_AVAILABLE",
    "ConfidenceCalculator",
    "ConfidenceResult",
    "ConfidenceLevel",
    "TORCH_AVAILABLE",
    "ResponseValidator",
    "ValidationResult",
    "ValidationIssue",
    "ValidationSeverity",
    "HallucinationDetector",
    "FinancialFactChecker",
    "CategoryValidator",
    "ResponseFormatter",
    "format_response",
    "DisclaimerGenerator",
]
