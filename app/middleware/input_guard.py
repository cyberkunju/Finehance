"""Input Guard - Protection against prompt injection attacks.

This module provides comprehensive protection against:
- Prompt injection attacks
- Jailbreak attempts
- Role/persona manipulation
- Instruction override attacks
- Malicious payload detection

Usage:
    from app.middleware.input_guard import InputGuard

    guard = InputGuard()
    result = guard.validate(user_input)

    if not result.is_safe:
        raise HTTPException(400, result.rejection_reason)
"""

import re
from dataclasses import dataclass, field
from enum import IntEnum
from typing import List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class ThreatLevel(IntEnum):
    """Threat level classification for detected issues.

    Uses IntEnum for proper numeric comparison (CRITICAL > HIGH > MEDIUM > LOW > NONE).
    """

    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

    @property
    def label(self) -> str:
        """Get human-readable label."""
        return self.name.lower()


@dataclass
class DetectedThreat:
    """A detected threat in the input."""

    pattern_name: str
    matched_text: str
    threat_level: ThreatLevel
    description: str


@dataclass
class InputValidationResult:
    """Result of input validation."""

    is_safe: bool
    original_input: str
    sanitized_input: Optional[str] = None
    threat_level: ThreatLevel = ThreatLevel.NONE
    detected_threats: List[DetectedThreat] = field(default_factory=list)
    rejection_reason: Optional[str] = None
    risk_score: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary for logging/API response."""
        return {
            "is_safe": self.is_safe,
            "threat_level": self.threat_level.label,
            "risk_score": self.risk_score,
            "threats_detected": len(self.detected_threats),
            "rejection_reason": self.rejection_reason,
        }


class InputGuard:
    """
    Input validation and sanitization for AI prompts.

    Detects and blocks prompt injection attacks, jailbreaks,
    and other malicious input patterns.

    Attributes:
        max_input_length: Maximum allowed input length
        risk_threshold: Score above which input is rejected (0-100)
        strict_mode: If True, any detected threat blocks input
    """

    # Instruction override patterns - attempts to change AI behavior
    INSTRUCTION_OVERRIDE_PATTERNS = [
        (
            r"ignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|rules?|guidelines?|prompts?)",
            "instruction_override",
            ThreatLevel.CRITICAL,
            20,
        ),
        (
            r"forget\s+(everything|all|what)\s+(you|i)\s+(told|said|learned)",
            "memory_erasure",
            ThreatLevel.CRITICAL,
            20,
        ),
        (
            r"forget\s+(all\s+)?(previous|prior|earlier)\s+(instructions?|rules?|prompts?)",
            "memory_erasure_v2",
            ThreatLevel.CRITICAL,
            20,
        ),
        (
            r"disregard\s+(all\s+)?(your|the|my)\s+(instructions?|training|rules?)",
            "disregard_command",
            ThreatLevel.CRITICAL,
            20,
        ),
        (
            r"override\s+(your|the|system)\s+(instructions?|rules?|settings?)",
            "override_attempt",
            ThreatLevel.CRITICAL,
            20,
        ),
        (r"new\s+instructions?\s*[:\-]", "new_instructions", ThreatLevel.HIGH, 15),
        (
            r"from\s+now\s+on[,\s]+(you\s+)?(are|will|must|should)",
            "behavior_change",
            ThreatLevel.HIGH,
            15,
        ),
        (
            r"stop\s+being\s+(a\s+)?(helpful|assistant|ai|safe)",
            "role_rejection",
            ThreatLevel.HIGH,
            15,
        ),
    ]

    # Role/persona manipulation - attempts to change AI identity
    ROLE_MANIPULATION_PATTERNS = [
        (
            r"you\s+are\s+(now|actually|really)\s+(a|an|the)",
            "role_assignment",
            ThreatLevel.HIGH,
            15,
        ),
        (
            r"you\s+are\s+now\s+(DAN|jailbroken|unrestricted|unlimited)",
            "role_assignment_jailbreak",
            ThreatLevel.CRITICAL,
            25,
        ),
        (r"pretend\s+(to\s+be|you\s+are|that\s+you)", "pretend_command", ThreatLevel.MEDIUM, 10),
        (
            r"pretend\s+you\s+have\s+no\s+(restrictions?|limits?|rules?|boundaries)",
            "pretend_unrestricted",
            ThreatLevel.CRITICAL,
            25,
        ),
        (r"act\s+(as\s+if|like)\s+you\s+(are|were|have)", "act_as_command", ThreatLevel.MEDIUM, 10),
        (r"roleplay\s+(as|that|where)\s+you", "roleplay_command", ThreatLevel.MEDIUM, 10),
        (
            r"imagine\s+you\s+(are|were|have)\s+(no|unlimited|free)",
            "imagination_exploit",
            ThreatLevel.HIGH,
            15,
        ),
        (
            r"(DAN|jailbreak|uncensored|unfiltered)\s*mode",
            "jailbreak_mode",
            ThreatLevel.CRITICAL,
            25,
        ),
        (
            r"developer\s+mode\s*(enabled|activated|on)",
            "developer_mode_exploit",
            ThreatLevel.CRITICAL,
            25,
        ),
        (r"enable\s+developer\s+mode", "developer_mode_enable", ThreatLevel.CRITICAL, 25),
        (
            r"bypass\s+(safety|security|restrictions?|filters?)",
            "bypass_safety",
            ThreatLevel.CRITICAL,
            25,
        ),
    ]

    # System prompt extraction attempts
    SYSTEM_PROMPT_EXTRACTION = [
        (
            r"(show|reveal|display|print|output|tell)\s+.{0,20}(your|the|system)\s+(prompt|instructions?|rules?)",
            "prompt_extraction",
            ThreatLevel.HIGH,
            15,
        ),
        (
            r"what\s+(are|were|is)\s+.{0,20}(original|initial|system)\s+(instructions?|prompt)",
            "prompt_query",
            ThreatLevel.MEDIUM,
            10,
        ),
        (
            r"repeat\s+.{0,15}(system|initial)\s+(message|prompt|instructions?)",
            "prompt_repeat",
            ThreatLevel.HIGH,
            15,
        ),
        (
            r"(beginning|start)\s+of\s+(the\s+)?(conversation|prompt|instructions?)",
            "prompt_beginning",
            ThreatLevel.MEDIUM,
            10,
        ),
        (r"(system|hidden|secret)\s+prompt", "system_prompt_mention", ThreatLevel.MEDIUM, 10),
    ]

    # Code injection and special character attacks
    CODE_INJECTION_PATTERNS = [
        (r"<\s*script[^>]*>", "script_tag_injection", ThreatLevel.CRITICAL, 25),
        (
            r"(execute|run)\s+(this\s+)?(script|command|code)",
            "script_execution",
            ThreatLevel.CRITICAL,
            25,
        ),
        (r"\brm\s+-rf\b", "destructive_command", ThreatLevel.CRITICAL, 25),
        (r"\{\{\s*.*?\s*\}\}", "template_injection", ThreatLevel.HIGH, 15),
        (r"\$\{[^}]+\}", "variable_injection", ThreatLevel.HIGH, 15),
        (r"__[a-zA-Z]+__", "dunder_access", ThreatLevel.MEDIUM, 10),
        (r"eval\s*\(|exec\s*\(|compile\s*\(", "code_execution", ThreatLevel.CRITICAL, 25),
        (r"import\s+(os|sys|subprocess|shutil)", "dangerous_import", ThreatLevel.CRITICAL, 25),
    ]

    # Financial-specific dangerous patterns
    FINANCIAL_DANGEROUS_PATTERNS = [
        (
            r"(transfer|send|wire)\s+all\s+(my|the)\s+(money|funds|balance)",
            "fund_transfer_all",
            ThreatLevel.CRITICAL,
            25,
        ),
        (
            r"(give|tell|show|reveal)\s+me\s+.{0,30}(api|secret|private|access)\s*key",
            "credential_extraction",
            ThreatLevel.CRITICAL,
            25,
        ),
        (r"(password|credentials?|secrets?)\s*(is|are|:)", "credential_leak", ThreatLevel.HIGH, 15),
        (
            r"(access|hack|breach|exploit)\s+(the\s+)?(account|system|database)",
            "unauthorized_access",
            ThreatLevel.CRITICAL,
            25,
        ),
    ]

    # Boundary/delimiter manipulation
    DELIMITER_ATTACKS = [
        (r"---+\s*(system|user|assistant)\s*---+", "role_delimiter", ThreatLevel.HIGH, 15),
        (
            r"\[INST\]|\[\/INST\]|\<\|im_start\|\>|\<\|im_end\|\>",
            "instruction_tag",
            ThreatLevel.CRITICAL,
            20,
        ),
        (
            r"<\|system\|>|<\|user\|>|<\|assistant\|>",
            "role_tag_injection",
            ThreatLevel.CRITICAL,
            20,
        ),
        (r"(USER|SYSTEM|ASSISTANT)\s*:", "role_prefix", ThreatLevel.MEDIUM, 10),
        (r"###\s*(System|Instruction|Human|Assistant)", "markdown_role", ThreatLevel.MEDIUM, 10),
    ]

    # Obfuscation detection
    OBFUSCATION_PATTERNS = [
        (r"(?:[a-zA-Z]\s){5,}", "spaced_letters", ThreatLevel.MEDIUM, 10),
        (r"(?:[\u200b-\u200f\u2060-\u206f])", "invisible_characters", ThreatLevel.HIGH, 15),
        (r"(?:[a-zA-Z][0-9]){3,}", "letter_number_mix", ThreatLevel.LOW, 5),
        (r"\\x[0-9a-fA-F]{2}", "hex_encoding", ThreatLevel.MEDIUM, 10),
        (r"\\u[0-9a-fA-F]{4}", "unicode_encoding", ThreatLevel.MEDIUM, 10),
    ]

    def __init__(
        self,
        max_input_length: int = 4000,
        risk_threshold: float = 25.0,
        strict_mode: bool = False,
        log_threats: bool = True,
    ):
        """
        Initialize InputGuard.

        Args:
            max_input_length: Maximum allowed characters (default 4000)
            risk_threshold: Score above which input is rejected (0-100)
            strict_mode: If True, any HIGH/CRITICAL threat blocks input
            log_threats: Whether to log detected threats
        """
        self.max_input_length = max_input_length
        self.risk_threshold = risk_threshold
        self.strict_mode = strict_mode
        self.log_threats = log_threats

        # Compile all patterns for efficiency
        self._compiled_patterns = self._compile_patterns()

    def _compile_patterns(self) -> List[Tuple[re.Pattern, str, ThreatLevel, int]]:
        """Compile all regex patterns for efficient matching."""
        all_patterns = (
            self.INSTRUCTION_OVERRIDE_PATTERNS
            + self.ROLE_MANIPULATION_PATTERNS
            + self.SYSTEM_PROMPT_EXTRACTION
            + self.CODE_INJECTION_PATTERNS
            + self.FINANCIAL_DANGEROUS_PATTERNS
            + self.DELIMITER_ATTACKS
            + self.OBFUSCATION_PATTERNS
        )

        compiled = []
        for pattern, name, level, score in all_patterns:
            try:
                compiled.append(
                    (re.compile(pattern, re.IGNORECASE | re.MULTILINE), name, level, score)
                )
            except re.error as e:
                logger.error(f"Failed to compile pattern '{name}': {e}")

        return compiled

    def validate(self, input_text: str) -> InputValidationResult:
        """
        Validate input text for potential threats.

        Args:
            input_text: The user input to validate

        Returns:
            InputValidationResult with safety status and details
        """
        if not input_text:
            return InputValidationResult(
                is_safe=True,
                original_input="",
                sanitized_input="",
                threat_level=ThreatLevel.NONE,
            )

        detected_threats: List[DetectedThreat] = []
        total_risk_score = 0.0

        # Check length first
        if len(input_text) > self.max_input_length:
            return InputValidationResult(
                is_safe=False,
                original_input=input_text[:100] + "...",
                threat_level=ThreatLevel.MEDIUM,
                rejection_reason=f"Input too long ({len(input_text)} chars, max {self.max_input_length})",
                risk_score=30.0,
            )

        # Check for excessive repetition (often used in attacks)
        repetition_threat = self._check_repetition(input_text)
        if repetition_threat:
            detected_threats.append(repetition_threat)
            total_risk_score += 15.0

        # Run all pattern checks
        for pattern, name, level, score in self._compiled_patterns:
            matches = pattern.findall(input_text)
            if matches:
                for match in matches[:3]:  # Limit matches to prevent DoS
                    match_text = match if isinstance(match, str) else match[0]
                    detected_threats.append(
                        DetectedThreat(
                            pattern_name=name,
                            matched_text=match_text[:50],  # Truncate for safety
                            threat_level=level,
                            description=f"Detected {name} pattern",
                        )
                    )
                    total_risk_score += score

        # Determine overall threat level
        max_threat = ThreatLevel.NONE
        for threat in detected_threats:
            if threat.threat_level > max_threat:
                max_threat = threat.threat_level

        # Determine if input should be blocked
        is_safe = True
        rejection_reason = None

        if self.strict_mode and max_threat in (ThreatLevel.HIGH, ThreatLevel.CRITICAL):
            is_safe = False
            rejection_reason = f"Strict mode: {max_threat.label} threat detected - {detected_threats[0].pattern_name}"
        elif total_risk_score >= self.risk_threshold:
            is_safe = False
            rejection_reason = (
                f"Risk score {total_risk_score:.1f} exceeds threshold {self.risk_threshold}"
            )
        elif max_threat == ThreatLevel.CRITICAL:
            is_safe = False
            rejection_reason = f"Critical threat detected: {detected_threats[0].pattern_name}"

        # Log threats if configured
        if self.log_threats and detected_threats:
            logger.warning(
                "Input threats detected",
                extra={
                    "threat_count": len(detected_threats),
                    "max_threat_level": max_threat.value,
                    "risk_score": total_risk_score,
                    "is_blocked": not is_safe,
                    "patterns": [t.pattern_name for t in detected_threats[:5]],
                },
            )

        # Create sanitized version (remove detected patterns)
        sanitized = input_text
        if detected_threats and is_safe:
            sanitized = self._sanitize_input(input_text)

        return InputValidationResult(
            is_safe=is_safe,
            original_input=input_text,
            sanitized_input=sanitized if is_safe else None,
            threat_level=max_threat,
            detected_threats=detected_threats,
            rejection_reason=rejection_reason,
            risk_score=total_risk_score,
        )

    def _check_repetition(self, text: str) -> Optional[DetectedThreat]:
        """Check for suspicious repetition patterns."""
        # Check for repeated words
        words = text.lower().split()
        if len(words) > 5:
            word_counts = {}
            for word in words:
                word_counts[word] = word_counts.get(word, 0) + 1

            for word, count in word_counts.items():
                if count > 10 and len(word) > 3:
                    return DetectedThreat(
                        pattern_name="excessive_repetition",
                        matched_text=f"'{word}' repeated {count} times",
                        threat_level=ThreatLevel.MEDIUM,
                        description="Excessive word repetition detected",
                    )

        # Check for repeated characters
        if re.search(r"(.)\1{10,}", text):
            return DetectedThreat(
                pattern_name="char_repetition",
                matched_text="Repeated characters",
                threat_level=ThreatLevel.MEDIUM,
                description="Excessive character repetition detected",
            )

        return None

    def _sanitize_input(self, text: str) -> str:
        """
        Remove or neutralize potentially harmful patterns.

        This is a light sanitization for inputs that pass validation
        but have low-risk patterns detected.
        """
        sanitized = text

        # Remove invisible characters
        sanitized = re.sub(r"[\u200b-\u200f\u2060-\u206f]", "", sanitized)

        # Normalize excessive whitespace
        sanitized = re.sub(r"\s{3,}", "  ", sanitized)

        # Remove potential template markers
        sanitized = re.sub(r"\{\{[^}]*\}\}", "[removed]", sanitized)

        return sanitized.strip()

    def get_safe_preview(self, text: str, max_length: int = 100) -> str:
        """Get a safe preview of input for logging."""
        if not text:
            return ""
        preview = text[:max_length]
        if len(text) > max_length:
            preview += "..."
        # Remove potential log injection characters
        preview = re.sub(r"[\n\r\t]", " ", preview)
        return preview


# Convenience function for quick validation
def validate_input(text: str, **kwargs) -> InputValidationResult:
    """
    Convenience function to validate input without creating a guard instance.

    Args:
        text: Input text to validate
        **kwargs: Arguments to pass to InputGuard constructor

    Returns:
        InputValidationResult
    """
    guard = InputGuard(**kwargs)
    return guard.validate(text)
