"""
AI Response Validation Module.

Provides validation for AI-generated financial content including:
- Hallucination detection (fabricated numbers, facts)
- Financial fact-checking (unrealistic claims)
- Category validation (merchant → category mapping)
- Response quality checks
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Set, Tuple
import logging

logger = logging.getLogger(__name__)


class ValidationSeverity(Enum):
    """Severity of validation issues."""
    INFO = "info"           # Minor, informational
    WARNING = "warning"     # Should review
    ERROR = "error"         # Significant issue
    CRITICAL = "critical"   # Block response


@dataclass
class ValidationIssue:
    """A single validation issue found."""
    type: str
    message: str
    severity: ValidationSeverity
    context: Optional[str] = None
    suggestion: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "message": self.message,
            "severity": self.severity.value,
            "context": self.context,
            "suggestion": self.suggestion,
        }


@dataclass
class ValidationResult:
    """Complete validation result."""
    is_valid: bool
    score: float  # 0-1, higher is better
    issues: List[ValidationIssue] = field(default_factory=list)
    corrections: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "score": round(self.score, 3),
            "issues": [i.to_dict() for i in self.issues],
            "corrections": self.corrections,
        }


# =============================================================================
# Hallucination Detection
# =============================================================================

class HallucinationDetector:
    """
    Detect hallucinated content in AI responses.
    
    Identifies:
    - Fabricated specific numbers not in context
    - Made-up percentages and statistics
    - Assumed user data (income, accounts)
    - Non-existent sources or references
    """
    
    # Patterns for detecting hallucinations
    HALLUCINATION_PATTERNS = [
        # Fabricated specific amounts
        (r"\$[\d,]+\.\d{2}\s+(?:per|each|every)\s+(?:month|week|year)", 
         "fabricated_amount", "Specific amount may be fabricated"),
        
        # Made-up percentages with decimals (too specific)
        (r"\b\d{1,2}\.\d{2,}%", 
         "overly_precise_percentage", "Percentage is suspiciously precise"),
        
        # Assumed income references
        (r"(?:your|based on your)\s+(?:income|salary|earnings)\s+of\s+\$[\d,]+",
         "assumed_income", "Income amount was not provided by user"),
        
        # Fabricated account balances
        (r"(?:your|in your)\s+(?:account|balance|savings)\s+(?:of|is|has)\s+\$[\d,]+",
         "assumed_balance", "Account balance was not provided"),
        
        # Fake data access claims
        (r"(?:according to|based on|from)\s+your\s+(?:records|data|history|transactions)",
         "fake_data_access", "AI does not have access to actual records"),
        
        # Made-up transaction counts
        (r"you\s+(?:made|have|had)\s+(?:exactly\s+)?\d+\s+transactions?",
         "fabricated_transaction_count", "Transaction count may be fabricated"),
        
        # Invented sources
        (r"(?:according to|studies show|research indicates|data shows)",
         "unverified_source", "Claims unverified external source"),
    ]
    
    # Numbers that are likely hallucinated if not in context
    SUSPICIOUS_SPECIFICITY = [
        r"\$\d{4,}\.\d{2}(?!\d)",  # Amounts with cents (too specific)
        r"\b\d+\.\d{3,}%",         # Percentages with 3+ decimals
        r"\b(?:approximately|about|around)\s+\$[\d,]+\.\d{2}",  # "Approximately" with exact cents
    ]
    
    def __init__(self):
        self.compiled_patterns = [
            (re.compile(p, re.IGNORECASE), name, msg) 
            for p, name, msg in self.HALLUCINATION_PATTERNS
        ]
        self.specificity_patterns = [
            re.compile(p, re.IGNORECASE) 
            for p in self.SUSPICIOUS_SPECIFICITY
        ]
    
    def detect(
        self,
        response: str,
        context: Optional[Dict[str, Any]] = None,
        mode: str = "chat",
    ) -> List[ValidationIssue]:
        """
        Detect potential hallucinations in the response.
        
        Args:
            response: AI-generated response text
            context: User context that was provided
            mode: Response mode (chat, analyze, parse)
            
        Returns:
            List of validation issues found
        """
        issues = []
        context = context or {}
        
        # Check against known patterns
        for pattern, issue_type, message in self.compiled_patterns:
            matches = pattern.findall(response)
            for match in matches:
                # Check if value exists in context
                if not self._value_in_context(match, context):
                    issues.append(ValidationIssue(
                        type=f"hallucination_{issue_type}",
                        message=message,
                        severity=ValidationSeverity.WARNING,
                        context=match if isinstance(match, str) else str(match),
                    ))
        
        # Check for suspicious specificity
        for pattern in self.specificity_patterns:
            matches = pattern.findall(response)
            for match in matches:
                if not self._value_in_context(match, context):
                    issues.append(ValidationIssue(
                        type="hallucination_suspicious_specificity",
                        message="Value appears fabricated (too specific)",
                        severity=ValidationSeverity.INFO,
                        context=match,
                    ))
        
        # Check for numbers referenced without context
        if mode == "analyze" and context:
            issues.extend(self._check_number_grounding(response, context))
        
        return issues
    
    def _value_in_context(self, value: str, context: Dict) -> bool:
        """Check if a specific value exists in the provided context."""
        context_str = str(context).lower()
        value_str = str(value).lower()
        
        # Extract just the number portion for comparison
        numbers = re.findall(r'[\d,]+\.?\d*', value_str)
        for num in numbers:
            clean_num = num.replace(',', '')
            if clean_num in context_str:
                return True
        
        return False
    
    def _check_number_grounding(
        self,
        response: str,
        context: Dict,
    ) -> List[ValidationIssue]:
        """Check that numbers in response are grounded in context."""
        issues = []
        
        # Extract all dollar amounts from response
        amounts = re.findall(r'\$[\d,]+(?:\.\d{2})?', response)
        context_str = str(context)
        
        for amount in amounts:
            clean_amount = amount.replace('$', '').replace(',', '')
            # Allow common amounts that might be suggestions
            if float(clean_amount) not in [50, 100, 200, 500, 1000, 2000, 5000]:
                if clean_amount not in context_str:
                    issues.append(ValidationIssue(
                        type="hallucination_ungrounded_amount",
                        message=f"Amount {amount} not found in provided context",
                        severity=ValidationSeverity.WARNING,
                        context=amount,
                        suggestion="Consider using relative terms or context values",
                    ))
        
        return issues


# =============================================================================
# Financial Fact Checker
# =============================================================================

class FinancialFactChecker:
    """
    Validate financial advice for accuracy and safety.
    
    Detects:
    - Unrealistic return promises
    - Dangerous financial advice
    - Mathematically impossible claims
    - Regulatory/legal issues
    """
    
    # Realistic bounds for financial metrics
    REALISTIC_BOUNDS = {
        "annual_return_max": 30.0,           # Max realistic annual return %
        "guaranteed_return_max": 5.0,         # Max for "guaranteed" returns
        "savings_rate_max": 80.0,            # Max savings rate %
        "debt_interest_min": 0.0,            # Min realistic APR
        "debt_interest_max": 36.0,           # Max realistic APR (predatory)
        "emergency_fund_months_min": 3,      # Minimum recommended
        "emergency_fund_months_max": 12,     # Maximum recommended
    }
    
    # Dangerous advice patterns
    DANGEROUS_ADVICE_PATTERNS = [
        # Guaranteed returns
        (r"guaranteed?\s+(?:to\s+)?(?:return|earn|make|get)\s+\d+%",
         "guaranteed_returns", ValidationSeverity.ERROR),
        
        # YOLO investing advice
        (r"(?:put|invest)\s+(?:all|everything|100%)\s+(?:of\s+)?(?:your|money|savings)",
         "all_in_investment", ValidationSeverity.WARNING),
        
        # Skip essential payments
        (r"(?:skip|don't pay|ignore)\s+(?:your\s+)?(?:rent|mortgage|insurance|taxes)",
         "skip_essential_payment", ValidationSeverity.CRITICAL),
        
        # Crypto/gambling as investment
        (r"(?:invest|put)\s+(?:in|money into)\s+(?:crypto|bitcoin|gambling|lottery)",
         "high_risk_recommendation", ValidationSeverity.WARNING),
        
        # No emergency fund
        (r"(?:don't need|skip|ignore)\s+(?:an?\s+)?emergency\s+fund",
         "skip_emergency_fund", ValidationSeverity.WARNING),
        
        # Tax evasion
        (r"(?:don't report|hide|avoid paying)\s+(?:your\s+)?taxes?",
         "tax_evasion", ValidationSeverity.CRITICAL),
        
        # Unrealistic timelines
        (r"(?:become|get)\s+(?:rich|wealthy|millionaire)\s+(?:in|within)\s+\d+\s+(?:days?|weeks?|months?)",
         "unrealistic_timeline", ValidationSeverity.ERROR),
    ]
    
    # Mathematical impossibilities
    IMPOSSIBLE_CLAIMS = [
        (r"earn\s+\$?\d+\s+working\s+0\s+hours?", "zero_effort_income"),
        (r"(?:double|triple)\s+your\s+money\s+(?:overnight|instantly|immediately)", "instant_multiplication"),
        (r"100%\s+(?:risk-?free|safe)\s+(?:investment|return)", "risk_free_investment"),
    ]
    
    def __init__(self):
        self.dangerous_patterns = [
            (re.compile(p, re.IGNORECASE), name, sev)
            for p, name, sev in self.DANGEROUS_ADVICE_PATTERNS
        ]
        self.impossible_patterns = [
            (re.compile(p, re.IGNORECASE), name)
            for p, name in self.IMPOSSIBLE_CLAIMS
        ]
    
    def check(
        self,
        response: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[ValidationIssue]:
        """
        Check response for financial accuracy and safety.
        
        Args:
            response: AI-generated response
            context: User financial context
            
        Returns:
            List of validation issues
        """
        issues = []
        
        # Check for dangerous advice patterns
        for pattern, issue_type, severity in self.dangerous_patterns:
            if pattern.search(response):
                issues.append(ValidationIssue(
                    type=f"dangerous_advice_{issue_type}",
                    message=self._get_advice_warning(issue_type),
                    severity=severity,
                    suggestion=self._get_safe_alternative(issue_type),
                ))
        
        # Check for impossible claims
        for pattern, issue_type in self.impossible_patterns:
            if pattern.search(response):
                issues.append(ValidationIssue(
                    type=f"impossible_claim_{issue_type}",
                    message="Claim is mathematically impossible",
                    severity=ValidationSeverity.ERROR,
                ))
        
        # Check percentage bounds
        issues.extend(self._check_percentage_bounds(response))
        
        # Check for missing disclaimers on high-risk topics
        issues.extend(self._check_disclaimers(response))
        
        return issues
    
    def _check_percentage_bounds(self, response: str) -> List[ValidationIssue]:
        """Check that percentages are within realistic bounds."""
        issues = []
        
        # Find return percentages
        return_matches = re.findall(
            r'(?:return|earn|make|gain)\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*%',
            response,
            re.IGNORECASE
        )
        
        for match in return_matches:
            pct = float(match)
            if pct > self.REALISTIC_BOUNDS["annual_return_max"]:
                issues.append(ValidationIssue(
                    type="unrealistic_return",
                    message=f"Return of {pct}% exceeds realistic expectations",
                    severity=ValidationSeverity.WARNING,
                    context=f"{pct}%",
                    suggestion=f"Historical average market returns are 7-10% annually",
                ))
        
        return issues
    
    def _check_disclaimers(self, response: str) -> List[ValidationIssue]:
        """Check for missing disclaimers on sensitive topics."""
        issues = []
        
        sensitive_topics = {
            "investment": r"\b(?:invest|investment|stock|bond|portfolio)\b",
            "tax": r"\b(?:tax|deduct|irs|filing)\b",
            "insurance": r"\b(?:insurance|coverage|policy)\b",
            "debt": r"\b(?:debt|loan|credit|borrow)\b",
        }
        
        disclaimer_patterns = [
            r"(?:consult|speak with|see)\s+(?:a\s+)?(?:professional|advisor|accountant|lawyer)",
            r"(?:this is not|not|does not constitute)\s+(?:financial|legal|tax)\s+advice",
            r"(?:for informational purposes|educational purposes)\s+only",
        ]
        
        has_disclaimer = any(
            re.search(p, response, re.IGNORECASE) 
            for p in disclaimer_patterns
        )
        
        for topic, pattern in sensitive_topics.items():
            if re.search(pattern, response, re.IGNORECASE):
                if not has_disclaimer:
                    issues.append(ValidationIssue(
                        type="missing_disclaimer",
                        message=f"Response discusses {topic} without appropriate disclaimer",
                        severity=ValidationSeverity.INFO,
                        suggestion=f"Consider adding 'consult a {topic} professional' disclaimer",
                    ))
                    break  # Only one missing disclaimer warning
        
        return issues
    
    def _get_advice_warning(self, issue_type: str) -> str:
        """Get appropriate warning message for issue type."""
        warnings = {
            "guaranteed_returns": "Guaranteed returns are unrealistic and potentially fraudulent",
            "all_in_investment": "Putting all money in one investment is high-risk",
            "skip_essential_payment": "Skipping essential payments can have severe consequences",
            "high_risk_recommendation": "High-risk investments require careful consideration",
            "skip_emergency_fund": "Emergency funds are essential for financial security",
            "tax_evasion": "Tax evasion is illegal and can result in penalties",
            "unrealistic_timeline": "Get-rich-quick timelines are unrealistic",
        }
        return warnings.get(issue_type, "Potentially harmful financial advice detected")
    
    def _get_safe_alternative(self, issue_type: str) -> str:
        """Get safe alternative suggestion."""
        alternatives = {
            "guaranteed_returns": "Mention that investments carry risk",
            "all_in_investment": "Recommend diversification across assets",
            "skip_essential_payment": "Suggest prioritizing essential payments",
            "high_risk_recommendation": "Balance with safer investment options",
            "skip_emergency_fund": "Recommend 3-6 months expenses in emergency fund",
            "tax_evasion": "Suggest legal tax optimization strategies",
            "unrealistic_timeline": "Focus on long-term wealth building",
        }
        return alternatives.get(issue_type, "Revise to provide safer advice")


# =============================================================================
# Category Validator (Merchant → Category Mapping)
# =============================================================================

class CategoryValidator:
    """
    Validate and correct transaction category assignments.
    
    Maintains accurate merchant → category mappings to fix
    common AI misclassifications.
    """
    
    # Correct merchant → category mappings
    MERCHANT_CATEGORY_MAP = {
        # Grocery stores (commonly miscategorized as restaurants)
        "whole foods": "Groceries",
        "whole foods market": "Groceries",
        "trader joe's": "Groceries",
        "trader joes": "Groceries",
        "costco": "Groceries",
        "costco wholesale": "Groceries",
        "safeway": "Groceries",
        "kroger": "Groceries",
        "publix": "Groceries",
        "aldi": "Groceries",
        "wegmans": "Groceries",
        "sprouts": "Groceries",
        "heb": "Groceries",
        "food lion": "Groceries",
        
        # Fast food (not fine dining)
        "mcdonald's": "Fast Food",
        "mcdonalds": "Fast Food",
        "burger king": "Fast Food",
        "wendy's": "Fast Food",
        "wendys": "Fast Food",
        "taco bell": "Fast Food",
        "chick-fil-a": "Fast Food",
        "chick fil a": "Fast Food",
        "chipotle": "Fast Food",
        "subway": "Fast Food",
        "dominos": "Fast Food",
        "pizza hut": "Fast Food",
        "papa johns": "Fast Food",
        "kfc": "Fast Food",
        "popeyes": "Fast Food",
        "five guys": "Fast Food",
        "in-n-out": "Fast Food",
        "whataburger": "Fast Food",
        
        # Coffee (often miscategorized)
        "starbucks": "Coffee & Beverages",
        "dunkin": "Coffee & Beverages",
        "dunkin donuts": "Coffee & Beverages",
        "peets coffee": "Coffee & Beverages",
        "dutch bros": "Coffee & Beverages",
        
        # Gas stations
        "shell": "Gas & Fuel",
        "chevron": "Gas & Fuel",
        "exxon": "Gas & Fuel",
        "mobil": "Gas & Fuel",
        "bp": "Gas & Fuel",
        "arco": "Gas & Fuel",
        "76": "Gas & Fuel",
        "circle k": "Gas & Fuel",
        "speedway": "Gas & Fuel",
        "wawa": "Gas & Fuel",
        "sheetz": "Gas & Fuel",
        
        # Retail (not grocery)
        "walmart": "Shopping & Retail",
        "target": "Shopping & Retail",
        "amazon": "Shopping & Retail",
        "best buy": "Shopping & Retail",
        "home depot": "Shopping & Retail",
        "lowes": "Shopping & Retail",
        "ikea": "Shopping & Retail",
        "bed bath beyond": "Shopping & Retail",
        "bed bath & beyond": "Shopping & Retail",
        "tj maxx": "Shopping & Retail",
        "marshalls": "Shopping & Retail",
        "ross": "Shopping & Retail",
        "kohls": "Shopping & Retail",
        "macys": "Shopping & Retail",
        "nordstrom": "Shopping & Retail",
        
        # Subscriptions
        "netflix": "Subscriptions",
        "spotify": "Subscriptions",
        "hulu": "Subscriptions",
        "disney+": "Subscriptions",
        "disney plus": "Subscriptions",
        "hbo max": "Subscriptions",
        "apple music": "Subscriptions",
        "amazon prime": "Subscriptions",
        "youtube premium": "Subscriptions",
        "audible": "Subscriptions",
        
        # Rideshare
        "uber": "Transportation",
        "lyft": "Transportation",
        "uber eats": "Food Delivery",
        "doordash": "Food Delivery",
        "grubhub": "Food Delivery",
        "postmates": "Food Delivery",
        "instacart": "Groceries",
        
        # Transfers (not income)
        "venmo": "Transfers",
        "venmo cashout": "Transfers",
        "zelle": "Transfers",
        "paypal": "Transfers",
        "cash app": "Transfers",
    }
    
    # Category aliases (normalize variations)
    CATEGORY_ALIASES = {
        "food & dining": "Food & Dining",
        "restaurants": "Food & Dining",
        "dining": "Food & Dining",
        "eating out": "Food & Dining",
        "grocery": "Groceries",
        "groceries": "Groceries",
        "supermarket": "Groceries",
        "fast food": "Fast Food",
        "quick service": "Fast Food",
        "shopping": "Shopping & Retail",
        "retail": "Shopping & Retail",
        "gas": "Gas & Fuel",
        "fuel": "Gas & Fuel",
        "gasoline": "Gas & Fuel",
        "transport": "Transportation",
        "transit": "Transportation",
        "uber/lyft": "Transportation",
        "subscription": "Subscriptions",
        "streaming": "Subscriptions",
        "transfer": "Transfers",
        "payment": "Transfers",
        "income": "Income",
        "salary": "Income",
        "paycheck": "Income",
    }
    
    def __init__(self):
        # Build lowercase lookup maps
        self._merchant_map = {k.lower(): v for k, v in self.MERCHANT_CATEGORY_MAP.items()}
        self._alias_map = {k.lower(): v for k, v in self.CATEGORY_ALIASES.items()}
    
    def validate_category(
        self,
        merchant: str,
        category: str,
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate and potentially correct a category assignment.
        
        Args:
            merchant: Merchant name
            category: Assigned category
            
        Returns:
            Tuple of (is_valid, corrected_category or None)
        """
        merchant_lower = merchant.lower().strip()
        
        # Check if merchant has a known correct category
        if merchant_lower in self._merchant_map:
            correct_category = self._merchant_map[merchant_lower]
            if self._categories_match(category, correct_category):
                return True, None
            else:
                return False, correct_category
        
        # Check for partial matches
        for known_merchant, correct_category in self._merchant_map.items():
            if known_merchant in merchant_lower or merchant_lower in known_merchant:
                if self._categories_match(category, correct_category):
                    return True, None
                else:
                    return False, correct_category
        
        # No known mapping, assume valid
        return True, None
    
    def normalize_category(self, category: str) -> str:
        """
        Normalize a category name to standard form.
        
        Args:
            category: Input category name
            
        Returns:
            Normalized category name
        """
        category_lower = category.lower().strip()
        return self._alias_map.get(category_lower, category)
    
    def _categories_match(self, cat1: str, cat2: str) -> bool:
        """Check if two categories match (considering aliases)."""
        norm1 = self.normalize_category(cat1).lower()
        norm2 = self.normalize_category(cat2).lower()
        return norm1 == norm2
    
    def validate_parsed_transaction(
        self,
        parsed_data: Dict[str, Any],
    ) -> ValidationResult:
        """
        Validate a parsed transaction result.
        
        Args:
            parsed_data: Parsed transaction data
            
        Returns:
            ValidationResult with corrections if needed
        """
        issues = []
        corrections = {}
        
        merchant = parsed_data.get("merchant", "")
        category = parsed_data.get("category", "")
        
        if merchant and category:
            is_valid, correct_category = self.validate_category(merchant, category)
            
            if not is_valid and correct_category:
                issues.append(ValidationIssue(
                    type="category_mismatch",
                    message=f"'{merchant}' should be '{correct_category}', not '{category}'",
                    severity=ValidationSeverity.WARNING,
                    context=f"{merchant} → {category}",
                    suggestion=f"Correct category: {correct_category}",
                ))
                corrections["category"] = correct_category
        
        # Calculate validation score
        score = 1.0 - (len(issues) * 0.1)
        score = max(0.0, min(1.0, score))
        
        return ValidationResult(
            is_valid=len(issues) == 0,
            score=score,
            issues=issues,
            corrections=corrections,
        )


# =============================================================================
# Unified Response Validator
# =============================================================================

class ResponseValidator:
    """
    Unified validator combining all validation checks.
    """
    
    def __init__(self):
        self.hallucination_detector = HallucinationDetector()
        self.fact_checker = FinancialFactChecker()
        self.category_validator = CategoryValidator()
    
    def validate(
        self,
        response: str,
        mode: str = "chat",
        context: Optional[Dict[str, Any]] = None,
        parsed_data: Optional[Dict[str, Any]] = None,
    ) -> ValidationResult:
        """
        Run all applicable validations on a response.
        
        Args:
            response: AI-generated response text
            mode: Response mode (chat, analyze, parse)
            context: User context provided
            parsed_data: Parsed data (for parse mode)
            
        Returns:
            Combined ValidationResult
        """
        all_issues = []
        corrections = {}
        
        # Run hallucination detection
        hallucination_issues = self.hallucination_detector.detect(
            response, context, mode
        )
        all_issues.extend(hallucination_issues)
        
        # Run financial fact checking
        fact_issues = self.fact_checker.check(response, context)
        all_issues.extend(fact_issues)
        
        # For parse mode, validate category
        if mode == "parse" and parsed_data:
            cat_result = self.category_validator.validate_parsed_transaction(parsed_data)
            all_issues.extend(cat_result.issues)
            corrections.update(cat_result.corrections)
        
        # Calculate overall score
        severity_penalties = {
            ValidationSeverity.INFO: 0.02,
            ValidationSeverity.WARNING: 0.1,
            ValidationSeverity.ERROR: 0.25,
            ValidationSeverity.CRITICAL: 0.5,
        }
        
        total_penalty = sum(
            severity_penalties.get(issue.severity, 0.1)
            for issue in all_issues
        )
        score = max(0.0, 1.0 - total_penalty)
        
        # Determine if valid (no critical issues)
        has_critical = any(
            issue.severity == ValidationSeverity.CRITICAL
            for issue in all_issues
        )
        is_valid = not has_critical and score >= 0.5
        
        return ValidationResult(
            is_valid=is_valid,
            score=score,
            issues=all_issues,
            corrections=corrections,
        )


# Singleton instance
response_validator = ResponseValidator()


def validate_response(
    response: str,
    mode: str = "chat",
    context: Optional[Dict] = None,
    parsed_data: Optional[Dict] = None,
) -> ValidationResult:
    """
    Convenience function to validate a response.
    
    Args:
        response: AI response text
        mode: Response mode
        context: User context
        parsed_data: Parsed transaction data
        
    Returns:
        ValidationResult
    """
    return response_validator.validate(response, mode, context, parsed_data)
