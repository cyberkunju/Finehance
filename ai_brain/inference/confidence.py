"""
Confidence Calculation Module for AI Brain.

Calculates real confidence scores from token log probabilities
instead of using hardcoded values.

This module provides:
- Token-level confidence from log probabilities
- Sequence-level confidence aggregation
- Mode-specific confidence adjustments
- Uncertainty estimation for financial advice
"""

from __future__ import annotations  # Enable forward references for type hints

import math
import sys
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Tuple, TYPE_CHECKING
from enum import Enum

# Type checking imports - these don't run at runtime
if TYPE_CHECKING:
    import torch as torch_type

# Torch is optional - only needed when running in AI Brain environment
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = None

# Numpy is optional - used for statistics but not strictly required
# On Python 3.13+ with certain numpy builds (MINGW), numpy crashes at import
NUMPY_AVAILABLE = False
np = None

# Only try numpy on stable Python versions
if sys.version_info < (3, 13):
    try:
        import numpy as np
        NUMPY_AVAILABLE = True
    except ImportError:
        NUMPY_AVAILABLE = False
        np = None


class ConfidenceLevel(Enum):
    """Confidence level classification."""
    VERY_HIGH = "very_high"      # >= 0.95
    HIGH = "high"                # >= 0.85
    MEDIUM = "medium"            # >= 0.70
    LOW = "low"                  # >= 0.50
    VERY_LOW = "very_low"        # < 0.50


@dataclass
class ConfidenceResult:
    """Detailed confidence calculation result."""
    score: float                      # Overall confidence (0-1)
    level: ConfidenceLevel            # Classification
    token_confidences: List[float]    # Per-token confidence
    min_token_confidence: float       # Lowest token confidence
    uncertainty: float                # Inverse of confidence (for risk)
    factors: Dict[str, float]         # Contributing factors
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": round(self.score, 4),
            "level": self.level.value,
            "min_token_confidence": round(self.min_token_confidence, 4),
            "uncertainty": round(self.uncertainty, 4),
            "factors": {k: round(v, 4) for k, v in self.factors.items()},
        }


class ConfidenceCalculator:
    """
    Calculate real confidence scores from model outputs.
    
    Uses token log probabilities to compute meaningful confidence
    instead of hardcoded values.
    """
    
    # Mode-specific base thresholds
    MODE_THRESHOLDS = {
        "chat": 0.7,      # Conversational is more flexible
        "analyze": 0.8,   # Analysis needs higher confidence
        "parse": 0.85,    # Parsing needs structured accuracy
    }
    
    # Penalty weights for low-confidence situations
    PENALTY_WEIGHTS = {
        "min_token": 0.3,          # Weight for minimum token confidence
        "variance": 0.2,           # Weight for confidence variance penalty
        "length_normalization": 0.1,  # Adjustment for response length
    }
    
    def __init__(
        self,
        temperature: float = 0.7,
        min_acceptable_confidence: float = 0.5,
    ):
        """
        Initialize confidence calculator.
        
        Args:
            temperature: Generation temperature (affects probability spread)
            min_acceptable_confidence: Floor for confidence scores
        """
        self.temperature = temperature
        self.min_acceptable = min_acceptable_confidence
    
    def calculate_from_logits(
        self,
        logits: "Any",  # torch.Tensor when torch available
        generated_ids: "Any",  # torch.Tensor when torch available
        mode: str = "chat",
    ) -> ConfidenceResult:
        """
        Calculate confidence from generation logits.
        
        Args:
            logits: Model output logits (seq_len, vocab_size)
            generated_ids: Generated token IDs
            mode: Generation mode (chat, analyze, parse)
            
        Returns:
            ConfidenceResult with detailed confidence information
        """
        if not TORCH_AVAILABLE:
            return self._create_default_result(mode)
            
        # Convert logits to probabilities
        probs = torch.softmax(logits / self.temperature, dim=-1)
        
        # Get probability of each generated token
        token_probs = []
        for i, token_id in enumerate(generated_ids):
            if i < len(probs):
                token_prob = probs[i, token_id].item()
                token_probs.append(token_prob)
        
        if not token_probs:
            return self._create_default_result(mode)
        
        return self._compute_confidence(token_probs, mode)
    
    def calculate_from_log_probs(
        self,
        log_probs: List[float],
        mode: str = "chat",
    ) -> ConfidenceResult:
        """
        Calculate confidence from log probabilities.
        
        Args:
            log_probs: List of log probabilities for generated tokens
            mode: Generation mode
            
        Returns:
            ConfidenceResult with detailed confidence information
        """
        # Convert log probs to probabilities
        token_probs = [math.exp(lp) for lp in log_probs]
        return self._compute_confidence(token_probs, mode)
    
    def calculate_from_scores(
        self,
        scores: "List[Any]",  # List[torch.Tensor] when torch available
        generated_ids: List[int],
        mode: str = "chat",
    ) -> ConfidenceResult:
        """
        Calculate confidence from generation scores (output of generate()).
        
        Args:
            scores: List of score tensors from model.generate(output_scores=True)
            generated_ids: List of generated token IDs
            mode: Generation mode
            
        Returns:
            ConfidenceResult with detailed confidence information
        """
        if not TORCH_AVAILABLE:
            return self._create_default_result(mode)
            
        token_probs = []
        
        for i, (score, token_id) in enumerate(zip(scores, generated_ids)):
            # Convert to probabilities
            probs = torch.softmax(score / self.temperature, dim=-1)
            
            # Handle batched vs single output
            if probs.dim() > 1:
                probs = probs[0]  # Take first batch item
            
            token_prob = probs[token_id].item()
            token_probs.append(token_prob)
        
        if not token_probs:
            return self._create_default_result(mode)
        
        return self._compute_confidence(token_probs, mode)
    
    def _compute_confidence(
        self,
        token_probs: List[float],
        mode: str,
    ) -> ConfidenceResult:
        """
        Compute overall confidence from token probabilities.
        
        Uses a weighted combination of:
        - Geometric mean of token probabilities (base score)
        - Minimum token probability (catches weak points)
        - Variance penalty (high variance = uncertainty)
        - Mode-specific adjustments
        """
        # Filter out zeros/negatives for log computation
        valid_probs = [p for p in token_probs if p > 0]
        if len(valid_probs) == 0:
            return self._create_default_result(mode)
        
        # 1. Geometric mean (more robust to outliers than arithmetic)
        log_probs = [math.log(p) for p in valid_probs]
        geometric_mean = math.exp(sum(log_probs) / len(log_probs))
        
        # 2. Minimum token probability (identifies weak points)
        min_prob = min(valid_probs)
        
        # 3. Variance penalty (high variance = model is uncertain)
        mean_prob = sum(valid_probs) / len(valid_probs)
        variance = sum((p - mean_prob) ** 2 for p in valid_probs) / len(valid_probs)
        variance_penalty = 1.0 - min(variance * 2, 0.3)  # Max 30% penalty
        
        # 4. Length normalization (longer responses may have lower avg)
        length_factor = 1.0
        if len(valid_probs) > 100:
            length_factor = 1.0 + 0.05 * (len(valid_probs) / 100)  # Slight boost
        
        # 5. Mode-specific base threshold
        base_threshold = self.MODE_THRESHOLDS.get(mode, 0.75)
        
        # Combine factors
        base_score = geometric_mean
        min_token_adjustment = min_prob * self.PENALTY_WEIGHTS["min_token"]
        variance_adjustment = variance_penalty * self.PENALTY_WEIGHTS["variance"]
        
        # Final score: weighted combination
        final_score = (
            base_score * 0.5 +
            min_token_adjustment +
            variance_adjustment +
            (length_factor - 1.0) * self.PENALTY_WEIGHTS["length_normalization"]
        )
        
        # Ensure score is in valid range
        final_score = max(self.min_acceptable, min(1.0, final_score))
        
        # Apply mode-specific scaling
        if final_score < base_threshold:
            # Scale down for below-threshold scores
            final_score = final_score * 0.9
        
        # Classify confidence level
        level = self._classify_confidence(final_score)
        
        return ConfidenceResult(
            score=final_score,
            level=level,
            token_confidences=token_probs,
            min_token_confidence=float(min_prob),
            uncertainty=1.0 - final_score,
            factors={
                "geometric_mean": float(geometric_mean),
                "min_token_prob": float(min_prob),
                "variance_penalty": float(variance_penalty),
                "length_factor": float(length_factor),
                "base_threshold": float(base_threshold),
            }
        )
    
    def _classify_confidence(self, score: float) -> ConfidenceLevel:
        """Classify confidence score into levels."""
        if score >= 0.95:
            return ConfidenceLevel.VERY_HIGH
        elif score >= 0.85:
            return ConfidenceLevel.HIGH
        elif score >= 0.70:
            return ConfidenceLevel.MEDIUM
        elif score >= 0.50:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.VERY_LOW
    
    def _create_default_result(self, mode: str) -> ConfidenceResult:
        """Create a default result when calculation fails."""
        base = self.MODE_THRESHOLDS.get(mode, 0.75)
        return ConfidenceResult(
            score=base * 0.8,  # Conservative default
            level=ConfidenceLevel.MEDIUM,
            token_confidences=[],
            min_token_confidence=0.0,
            uncertainty=1.0 - (base * 0.8),
            factors={"default": 1.0},
        )
    
    def should_add_disclaimer(self, result: ConfidenceResult) -> bool:
        """
        Check if a confidence disclaimer should be added.
        
        Args:
            result: Confidence calculation result
            
        Returns:
            True if disclaimer should be added
        """
        return result.level in [ConfidenceLevel.LOW, ConfidenceLevel.VERY_LOW]
    
    def get_disclaimer_text(self, result: ConfidenceResult) -> str:
        """
        Get appropriate disclaimer text for low confidence.
        
        Args:
            result: Confidence calculation result
            
        Returns:
            Disclaimer text to append to response
        """
        if result.level == ConfidenceLevel.VERY_LOW:
            return (
                "\n\n⚠️ **Note:** This response has lower confidence. "
                "Please verify this information with a financial professional "
                "before making any decisions."
            )
        elif result.level == ConfidenceLevel.LOW:
            return (
                "\n\n**Note:** This is a general suggestion. Your specific "
                "situation may require personalized advice from a financial advisor."
            )
        return ""


# Singleton instance
confidence_calculator = ConfidenceCalculator()


def calculate_confidence(
    logits_or_probs: Any,
    generated_ids: Optional[List[int]] = None,
    mode: str = "chat",
    input_type: str = "logits",
) -> ConfidenceResult:
    """
    Convenience function to calculate confidence.
    
    Args:
        logits_or_probs: Model output (logits, log_probs, or scores)
        generated_ids: Generated token IDs (required for logits)
        mode: Generation mode
        input_type: Type of input ("logits", "log_probs", "scores")
        
    Returns:
        ConfidenceResult
    """
    calc = confidence_calculator
    
    if input_type == "logits" and generated_ids is not None:
        return calc.calculate_from_logits(logits_or_probs, generated_ids, mode)
    elif input_type == "log_probs":
        return calc.calculate_from_log_probs(logits_or_probs, mode)
    elif input_type == "scores" and generated_ids is not None:
        return calc.calculate_from_scores(logits_or_probs, generated_ids, mode)
    else:
        return calc._create_default_result(mode)
