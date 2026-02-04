"""Output Guard - Content filtering for AI responses.

This module provides comprehensive protection against:
- Harmful financial advice
- Profanity and toxic content
- Hallucinated data (fabricated numbers)
- PII exposure (emails, SSNs, account numbers)
- Unprofessional or inappropriate content

Usage:
    from app.middleware.output_guard import OutputGuard
    
    guard = OutputGuard()
    result = guard.validate(ai_response)
    
    if not result.is_safe:
        # Use filtered version or reject
        response_text = result.filtered_content or "Unable to provide response"
"""

import re
from dataclasses import dataclass, field
from enum import IntEnum
from typing import List, Optional, Set, Tuple
import logging

logger = logging.getLogger(__name__)


class ContentIssueType(IntEnum):
    """Types of content issues detected."""
    NONE = 0
    PII_EXPOSURE = 1
    PROFANITY = 2
    TOXIC_CONTENT = 3
    HARMFUL_ADVICE = 4
    HALLUCINATION = 5
    UNPROFESSIONAL = 6
    LEGAL_RISK = 7


class Severity(IntEnum):
    """Severity level for content issues."""
    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class ContentIssue:
    """A detected content issue in the output."""
    issue_type: ContentIssueType
    severity: Severity
    description: str
    matched_text: str
    position: Optional[Tuple[int, int]] = None  # Start, end positions
    remediation: Optional[str] = None


@dataclass
class OutputValidationResult:
    """Result of output content validation."""
    is_safe: bool
    original_content: str
    filtered_content: Optional[str] = None
    issues: List[ContentIssue] = field(default_factory=list)
    max_severity: Severity = Severity.NONE
    needs_disclaimer: bool = False
    pii_detected: bool = False
    content_modified: bool = False
    
    def to_dict(self) -> dict:
        """Convert to dictionary for logging/API response."""
        return {
            "is_safe": self.is_safe,
            "max_severity": self.max_severity.name,
            "issues_count": len(self.issues),
            "pii_detected": self.pii_detected,
            "content_modified": self.content_modified,
            "needs_disclaimer": self.needs_disclaimer,
        }


class OutputGuard:
    """
    Content filtering and validation for AI responses.
    
    Detects and filters harmful content, PII, profanity,
    and potentially dangerous financial advice.
    
    Attributes:
        mask_pii: Whether to automatically mask detected PII
        filter_profanity: Whether to filter profanity
        require_disclaimer: Whether to flag responses needing disclaimers
        strict_mode: If True, any HIGH/CRITICAL issue blocks content
    """
    
    # PII Patterns - Very strict detection
    PII_PATTERNS = [
        # Social Security Numbers
        (r"\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b", 
         "ssn", ContentIssueType.PII_EXPOSURE, Severity.CRITICAL,
         "***-**-****"),
        
        # Credit Card Numbers (basic patterns)
        (r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b",
         "credit_card", ContentIssueType.PII_EXPOSURE, Severity.CRITICAL,
         "****-****-****-****"),
        
        # Bank Account Numbers (8-17 digits)
        (r"\b(?:account\s*(?:number|#|no\.?)?\s*[:.]?\s*)(\d{8,17})\b",
         "bank_account", ContentIssueType.PII_EXPOSURE, Severity.HIGH,
         "[ACCOUNT REDACTED]"),
        
        # Routing Numbers (9 digits)
        (r"\b(?:routing\s*(?:number|#|no\.?)?\s*[:.]?\s*)(\d{9})\b",
         "routing_number", ContentIssueType.PII_EXPOSURE, Severity.HIGH,
         "[ROUTING REDACTED]"),
        
        # Email addresses
        (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
         "email", ContentIssueType.PII_EXPOSURE, Severity.MEDIUM,
         "[EMAIL REDACTED]"),
        
        # Phone numbers (US format)
        (r"\b(?:\+?1[-.\s]?)?(?:\(?[0-9]{3}\)?[-.\s]?)[0-9]{3}[-.\s]?[0-9]{4}\b",
         "phone", ContentIssueType.PII_EXPOSURE, Severity.MEDIUM,
         "[PHONE REDACTED]"),
        
        # IP addresses
        (r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b",
         "ip_address", ContentIssueType.PII_EXPOSURE, Severity.LOW,
         "[IP REDACTED]"),
        
        # Dates of birth (various formats)
        (r"\b(?:dob|date\s*of\s*birth|born\s*on?)\s*[:.]?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b",
         "date_of_birth", ContentIssueType.PII_EXPOSURE, Severity.MEDIUM,
         "[DOB REDACTED]"),
    ]
    
    # Profanity and inappropriate language
    PROFANITY_PATTERNS = [
        # Strong profanity (would need actual list in production)
        # Note: 'ass' uses negative lookahead to avoid matching 'asset', 'assemble', etc.
        (r"\b(fuck|shit|ass(?!e[mnt])|bitch|damn|crap|bastard|dick|cock|pussy)\w*\b",
         "profanity", ContentIssueType.PROFANITY, Severity.MEDIUM),
        
        # Slurs and hate speech (condensed pattern)
        (r"\b(retard|idiot|moron|stupid\s+(?:user|customer|person))\w*\b",
         "insult", ContentIssueType.TOXIC_CONTENT, Severity.HIGH),
    ]
    
    # Harmful financial advice patterns
    HARMFUL_ADVICE_PATTERNS = [
        # Guarantees (legally problematic)
        (r"(?:i\s+)?(?:guarantee|promise|ensure)\s+(?:you(?:'ll)?|that\s+you)\s+(?:will\s+)?(?:make|earn|get|receive)\s+.{0,20}(?:money|profit|returns?|income|gains?)",
         "guarantee_returns", ContentIssueType.HARMFUL_ADVICE, Severity.CRITICAL,
         "Claiming guaranteed returns is illegal and misleading"),
        
        (r"(?:guaranteed|certain|sure|definite)\s+(?:profit|returns?|income|gains?|money)",
         "guaranteed_profit", ContentIssueType.HARMFUL_ADVICE, Severity.CRITICAL,
         "No investment returns are guaranteed"),
        
        # Verb form of guarantee + returns (catches "guarantees 50% returns")
        (r"guarantee[sd]?\s+.{0,30}(?:returns?|profit|gains?)",
         "guarantee_verb_returns", ContentIssueType.HARMFUL_ADVICE, Severity.CRITICAL,
         "Claiming guaranteed returns is misleading"),
        
        # Get rich quick schemes
        (r"(?:get\s+rich\s+quick|make\s+(?:fast|quick|easy)\s+money|double\s+your\s+money)",
         "get_rich_quick", ContentIssueType.HARMFUL_ADVICE, Severity.HIGH,
         "Promoting unrealistic wealth schemes"),
        
        # Risk minimization
        (r"(?:no\s+risk|risk.?free|zero\s+risk|without\s+(?:any\s+)?risk)\s+(?:investment|return|profit|money)",
         "no_risk_claim", ContentIssueType.HARMFUL_ADVICE, Severity.HIGH,
         "All investments carry risk"),
        
        # Standalone risk-free claims (with adverb modifiers)
        (r"(?:completely|totally|absolutely|entirely|100%)\s+risk.?free",
         "no_risk_standalone", ContentIssueType.HARMFUL_ADVICE, Severity.HIGH,
         "Nothing is completely risk-free"),
        
        # Specific stock/crypto recommendations
        (r"(?:buy|invest\s+in|put.+money\s+in)\s+(?:all\s+(?:of\s+)?your|100%|everything)\s+(?:into|in)\s+\w+",
         "all_in_recommendation", ContentIssueType.HARMFUL_ADVICE, Severity.HIGH,
         "Recommending putting all money in one asset is dangerous"),
        
        # Specific return percentages over 20%
        (r"(?:return|profit|gain|earn)\s+(?:of\s+)?(?:[2-9]\d|[1-9]\d{2,})%",
         "unrealistic_returns", ContentIssueType.HARMFUL_ADVICE, Severity.MEDIUM,
         "Promising very high returns without context"),
        
        # Tax evasion
        (r"(?:evade|avoid\s+paying|hide.+from)\s+(?:the\s+)?(?:irs|taxes|tax\s+authorities)",
         "tax_evasion", ContentIssueType.LEGAL_RISK, Severity.CRITICAL,
         "Promoting tax evasion is illegal"),
        
        # Debt advice that's dangerous
        (r"(?:just\s+)?(?:ignore|don't\s+pay|skip\s+paying)\s+(?:your\s+)?(?:debt|bills?|loans?|credit\s+cards?)",
         "ignore_debt", ContentIssueType.HARMFUL_ADVICE, Severity.HIGH,
         "Advising to ignore debt is harmful"),
        
        # Emergency fund misuse
        (r"(?:use|spend|invest)\s+(?:your\s+)?emergency\s+fund\s+(?:on|in|for)\s+(?:stocks?|crypto|invest)",
         "deplete_emergency", ContentIssueType.HARMFUL_ADVICE, Severity.HIGH,
         "Advising to invest emergency funds is risky"),
    ]
    
    # Hallucination indicators - fabricated specifics
    HALLUCINATION_PATTERNS = [
        # Specific percentages when not provided
        (r"(?:based\s+on|from|according\s+to)\s+(?:your|the)\s+(?:data|information|account).+?(\d+(?:\.\d+)?%)",
         "fabricated_percentage", ContentIssueType.HALLUCINATION, Severity.MEDIUM,
         "May be fabricating specific percentages"),
        
        # Specific dollar amounts with high precision
        (r"\$\d{1,3}(?:,\d{3})*\.\d{2}\s+(?:exactly|precisely|specifically)",
         "fabricated_amount", ContentIssueType.HALLUCINATION, Severity.MEDIUM,
         "May be fabricating specific amounts"),
        
        # "Your income/salary is..." without context
        (r"(?:your\s+)(?:income|salary|earnings?)\s+(?:is|are|of)\s+\$[\d,]+",
         "assumed_income", ContentIssueType.HALLUCINATION, Severity.MEDIUM,
         "May be assuming user's income without data"),
        
        # Claiming to see user data that wasn't provided
        (r"(?:i\s+(?:can\s+)?see|looking\s+at|reviewing)\s+(?:your|the)\s+(?:account|transactions?|history|records?)",
         "fake_data_access", ContentIssueType.HALLUCINATION, Severity.HIGH,
         "Claiming to access data that wasn't provided"),
        
        # Specific dates for predictions
        (r"(?:by|on|before)\s+(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2},?\s*\d{4}.+(?:you\s+will|you'll)\s+(?:have|reach|achieve)",
         "specific_prediction", ContentIssueType.HALLUCINATION, Severity.MEDIUM,
         "Making specific date predictions"),
    ]
    
    # Legal/disclaimer triggers - content that needs disclaimer
    DISCLAIMER_TRIGGERS = [
        r"(?:should|recommend|suggest)\s+(?:you\s+)?(?:invest|buy|sell)",
        r"(?:investment|financial|tax|legal)\s+advice",
        r"(?:stocks?|bonds?|mutual\s+funds?|etfs?|crypto)",
        r"(?:retirement|401k|ira|pension)",
        r"(?:insurance|annuit)",
        r"(?:loan|mortgage|credit)",
    ]
    
    # Standard financial disclaimer
    FINANCIAL_DISCLAIMER = (
        "\n\n---\n"
        "*This information is for educational purposes only and should not be considered "
        "financial advice. Please consult a qualified financial advisor for personalized "
        "recommendations. Past performance does not guarantee future results.*"
    )
    
    def __init__(
        self,
        mask_pii: bool = True,
        filter_profanity: bool = True,
        require_disclaimer: bool = True,
        strict_mode: bool = True,
        auto_add_disclaimer: bool = False,
        log_issues: bool = True,
    ):
        """
        Initialize OutputGuard.
        
        Args:
            mask_pii: Automatically mask detected PII
            filter_profanity: Filter or flag profanity
            require_disclaimer: Flag content needing financial disclaimers
            strict_mode: If True, HIGH/CRITICAL issues block content
            auto_add_disclaimer: Automatically append disclaimer when needed
            log_issues: Whether to log detected issues
        """
        self.mask_pii = mask_pii
        self.filter_profanity = filter_profanity
        self.require_disclaimer = require_disclaimer
        self.strict_mode = strict_mode
        self.auto_add_disclaimer = auto_add_disclaimer
        self.log_issues = log_issues
        
        # Compile patterns
        self._pii_patterns = self._compile_pii_patterns()
        self._profanity_patterns = self._compile_basic_patterns(self.PROFANITY_PATTERNS)
        self._harmful_patterns = self._compile_harmful_patterns()
        self._hallucination_patterns = self._compile_basic_patterns(self.HALLUCINATION_PATTERNS)
        self._disclaimer_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.DISCLAIMER_TRIGGERS
        ]
    
    def _compile_pii_patterns(self) -> List[Tuple[re.Pattern, str, ContentIssueType, Severity, str]]:
        """Compile PII patterns with replacement strings."""
        compiled = []
        for pattern, name, issue_type, severity, replacement in self.PII_PATTERNS:
            try:
                compiled.append((
                    re.compile(pattern, re.IGNORECASE),
                    name,
                    issue_type,
                    severity,
                    replacement
                ))
            except re.error as e:
                logger.error(f"Failed to compile PII pattern '{name}': {e}")
        return compiled
    
    def _compile_basic_patterns(
        self, 
        patterns: List[Tuple]
    ) -> List[Tuple[re.Pattern, str, ContentIssueType, Severity, Optional[str]]]:
        """Compile patterns with optional description."""
        compiled = []
        for item in patterns:
            pattern = item[0]
            name = item[1]
            issue_type = item[2]
            severity = item[3]
            description = item[4] if len(item) > 4 else None
            
            try:
                compiled.append((
                    re.compile(pattern, re.IGNORECASE),
                    name,
                    issue_type,
                    severity,
                    description
                ))
            except re.error as e:
                logger.error(f"Failed to compile pattern '{name}': {e}")
        return compiled
    
    def _compile_harmful_patterns(self) -> List[Tuple[re.Pattern, str, ContentIssueType, Severity, str]]:
        """Compile harmful advice patterns."""
        return self._compile_basic_patterns(self.HARMFUL_ADVICE_PATTERNS)
    
    def validate(self, content: str, context: Optional[dict] = None) -> OutputValidationResult:
        """
        Validate and optionally filter AI response content.
        
        Args:
            content: The AI response to validate
            context: Optional context about the request (user data provided, etc.)
            
        Returns:
            OutputValidationResult with safety status and filtered content
        """
        if not content or not content.strip():
            return OutputValidationResult(
                is_safe=True,
                original_content="",
                filtered_content="",
            )
        
        issues: List[ContentIssue] = []
        filtered = content
        pii_detected = False
        content_modified = False
        
        # Check for PII and mask if configured
        filtered, pii_issues = self._check_and_mask_pii(filtered)
        issues.extend(pii_issues)
        if pii_issues:
            pii_detected = True
            content_modified = True
        
        # Check for profanity
        if self.filter_profanity:
            filtered, profanity_issues = self._check_profanity(filtered)
            issues.extend(profanity_issues)
            if profanity_issues:
                content_modified = True
        
        # Check for harmful financial advice
        harmful_issues = self._check_harmful_advice(content)
        issues.extend(harmful_issues)
        
        # Check for hallucinations
        hallucination_issues = self._check_hallucinations(content, context)
        issues.extend(hallucination_issues)
        
        # Determine if disclaimer is needed
        needs_disclaimer = self._check_needs_disclaimer(content)
        
        # Add disclaimer if configured and needed
        if needs_disclaimer and self.auto_add_disclaimer:
            if self.FINANCIAL_DISCLAIMER not in filtered:
                filtered += self.FINANCIAL_DISCLAIMER
                content_modified = True
        
        # Calculate max severity
        max_severity = Severity.NONE
        for issue in issues:
            if issue.severity > max_severity:
                max_severity = issue.severity
        
        # Determine if content is safe
        is_safe = True
        if self.strict_mode and max_severity >= Severity.HIGH:
            is_safe = False
        elif max_severity == Severity.CRITICAL:
            is_safe = False
        
        # Log issues if configured
        if self.log_issues and issues:
            logger.warning(
                "Output content issues detected",
                extra={
                    "issue_count": len(issues),
                    "max_severity": max_severity.name,
                    "pii_detected": pii_detected,
                    "is_blocked": not is_safe,
                    "issue_types": [i.issue_type.name for i in issues[:5]],
                }
            )
        
        return OutputValidationResult(
            is_safe=is_safe,
            original_content=content,
            filtered_content=filtered if content_modified else content,
            issues=issues,
            max_severity=max_severity,
            needs_disclaimer=needs_disclaimer,
            pii_detected=pii_detected,
            content_modified=content_modified,
        )
    
    def _check_and_mask_pii(self, content: str) -> Tuple[str, List[ContentIssue]]:
        """Check for PII and mask it if configured."""
        issues = []
        masked = content
        
        for pattern, name, issue_type, severity, replacement in self._pii_patterns:
            matches = list(pattern.finditer(masked))
            for match in matches:
                issues.append(ContentIssue(
                    issue_type=issue_type,
                    severity=severity,
                    description=f"PII detected: {name}",
                    matched_text=match.group()[:20] + "...",  # Truncate for safety
                    position=(match.start(), match.end()),
                    remediation=f"Masked with {replacement}",
                ))
            
            if self.mask_pii and matches:
                masked = pattern.sub(replacement, masked)
        
        return masked, issues
    
    def _check_profanity(self, content: str) -> Tuple[str, List[ContentIssue]]:
        """Check for profanity and filter if configured."""
        issues = []
        filtered = content
        
        for pattern, name, issue_type, severity, _ in self._profanity_patterns:
            matches = list(pattern.finditer(filtered))
            for match in matches:
                issues.append(ContentIssue(
                    issue_type=issue_type,
                    severity=severity,
                    description=f"Inappropriate language: {name}",
                    matched_text="[PROFANITY]",  # Don't log actual word
                    position=(match.start(), match.end()),
                ))
            
            if matches:
                # Replace with asterisks
                filtered = pattern.sub(
                    lambda m: "*" * len(m.group()),
                    filtered
                )
        
        return filtered, issues
    
    def _check_harmful_advice(self, content: str) -> List[ContentIssue]:
        """Check for potentially harmful financial advice."""
        issues = []
        
        for pattern, name, issue_type, severity, description in self._harmful_patterns:
            matches = pattern.findall(content)
            if matches:
                # Only record first match to avoid spam
                match_text = matches[0] if isinstance(matches[0], str) else matches[0][0]
                issues.append(ContentIssue(
                    issue_type=issue_type,
                    severity=severity,
                    description=description or f"Harmful pattern: {name}",
                    matched_text=match_text[:50],
                    remediation="Content should be reviewed or blocked",
                ))
        
        return issues
    
    def _check_hallucinations(
        self, 
        content: str, 
        context: Optional[dict] = None
    ) -> List[ContentIssue]:
        """Check for potential hallucinations (fabricated data)."""
        issues = []
        
        for pattern, name, issue_type, severity, description in self._hallucination_patterns:
            matches = pattern.findall(content)
            if matches:
                # Check if this data was actually provided in context
                is_hallucination = True
                if context:
                    # If context provides relevant data, it's not a hallucination
                    match_text = matches[0] if isinstance(matches[0], str) else str(matches[0])
                    provided_data = context.get("user_provided_data", "")
                    if match_text in provided_data:
                        is_hallucination = False
                
                if is_hallucination:
                    issues.append(ContentIssue(
                        issue_type=issue_type,
                        severity=severity,
                        description=description or f"Potential hallucination: {name}",
                        matched_text=str(matches[0])[:50],
                        remediation="Verify this data was actually provided",
                    ))
        
        return issues
    
    def _check_needs_disclaimer(self, content: str) -> bool:
        """Check if content needs a financial disclaimer."""
        if not self.require_disclaimer:
            return False
        
        for pattern in self._disclaimer_patterns:
            if pattern.search(content):
                return True
        
        return False
    
    def get_safe_content(
        self, 
        content: str, 
        fallback: str = "I apologize, but I cannot provide that response.",
        context: Optional[dict] = None,
    ) -> str:
        """
        Get safe content - either filtered original or fallback.
        
        Args:
            content: Original AI response
            fallback: Fallback message if content is unsafe
            context: Optional context for validation
            
        Returns:
            Safe content string
        """
        result = self.validate(content, context)
        
        if result.is_safe:
            return result.filtered_content or content
        else:
            return fallback
    
    def quick_check(self, content: str) -> bool:
        """
        Quick safety check without full validation.
        
        Args:
            content: Content to check
            
        Returns:
            True if appears safe, False otherwise
        """
        # Check for critical PII
        for pattern, _, _, severity, _ in self._pii_patterns:
            if severity == Severity.CRITICAL and pattern.search(content):
                return False
        
        # Check for harmful advice
        for pattern, _, _, severity, _ in self._harmful_patterns:
            if severity == Severity.CRITICAL and pattern.search(content):
                return False
        
        return True


# Convenience function for quick validation
def validate_output(content: str, **kwargs) -> OutputValidationResult:
    """
    Convenience function to validate output without creating a guard instance.
    
    Args:
        content: Content to validate
        **kwargs: Arguments to pass to OutputGuard constructor
        
    Returns:
        OutputValidationResult
    """
    guard = OutputGuard(**kwargs)
    return guard.validate(content)


# Convenience function for getting safe content
def get_safe_response(
    content: str,
    fallback: str = "I cannot provide that response.",
    **kwargs
) -> str:
    """
    Get safe, filtered response content.
    
    Args:
        content: Original AI response
        fallback: Fallback if unsafe
        **kwargs: Arguments to pass to OutputGuard
        
    Returns:
        Safe response string
    """
    guard = OutputGuard(**kwargs)
    return guard.get_safe_content(content, fallback)
