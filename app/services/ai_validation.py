"""
AI Response Validation Service.

Provides cross-validation between AI Brain responses and ML model,
plus additional validation layers for the main application.

This service:
1. Cross-validates AI category predictions with ML model
2. Applies business rules for financial advice
3. Integrates validation with the main app response flow
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import re

logger = logging.getLogger(__name__)


class AgreementLevel(Enum):
    """Level of agreement between AI and ML predictions."""
    FULL = "full"           # Exact same category
    PARTIAL = "partial"     # Related categories (same parent)
    NONE = "none"           # Disagreement


@dataclass
class CrossValidationResult:
    """Result of AI vs ML cross-validation."""
    ai_category: str
    ml_category: str
    ml_confidence: float
    agreement: AgreementLevel
    final_category: str
    used_ml_override: bool = False
    explanation: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "ai_category": self.ai_category,
            "ml_category": self.ml_category,
            "ml_confidence": round(self.ml_confidence, 3),
            "agreement": self.agreement.value,
            "final_category": self.final_category,
            "used_ml_override": self.used_ml_override,
            "explanation": self.explanation,
        }


# Category hierarchy for partial matches
CATEGORY_HIERARCHY = {
    "Food & Dining": ["Groceries", "Fast Food", "Restaurants", "Coffee & Beverages", "Food Delivery"],
    "Transportation": ["Gas & Fuel", "Rideshare", "Parking", "Public Transit", "Car Services"],
    "Shopping": ["Shopping & Retail", "Electronics", "Clothing", "Home & Garden"],
    "Entertainment": ["Movies", "Games", "Streaming", "Events", "Hobbies"],
    "Bills & Utilities": ["Electric", "Gas", "Water", "Internet", "Phone"],
    "Financial": ["Transfers", "Investments", "Fees", "Interest", "Insurance"],
}

# Reverse lookup: category -> parent
CATEGORY_TO_PARENT = {}
for parent, children in CATEGORY_HIERARCHY.items():
    for child in children:
        CATEGORY_TO_PARENT[child.lower()] = parent


class AIMLCrossValidator:
    """
    Cross-validate AI Brain predictions with ML model.
    
    When AI and ML disagree, uses confidence levels and
    category-specific rules to determine final category.
    """
    
    # Threshold for ML override when AI confidence is low
    ML_OVERRIDE_THRESHOLD = 0.85
    
    # Categories where ML is preferred (training data is strong)
    ML_PREFERRED_CATEGORIES = {
        "Groceries", "Fast Food", "Gas & Fuel", "Subscriptions",
        "Transportation", "Shopping & Retail"
    }
    
    # Categories where AI is preferred (needs context understanding)
    AI_PREFERRED_CATEGORIES = {
        "Transfers", "Income", "Fees", "Other"
    }
    
    def __init__(self, ml_service=None):
        """
        Initialize validator.
        
        Args:
            ml_service: Optional ML categorization service for predictions
        """
        self.ml_service = ml_service
    
    async def cross_validate(
        self,
        transaction_description: str,
        ai_category: str,
        ai_confidence: float,
        ml_category: Optional[str] = None,
        ml_confidence: Optional[float] = None,
    ) -> CrossValidationResult:
        """
        Cross-validate AI category with ML prediction.
        
        Args:
            transaction_description: Original transaction text
            ai_category: Category from AI Brain
            ai_confidence: AI confidence score
            ml_category: Pre-computed ML category (optional)
            ml_confidence: Pre-computed ML confidence (optional)
            
        Returns:
            CrossValidationResult with final decision
        """
        # Get ML prediction if not provided
        if ml_category is None and self.ml_service:
            try:
                ml_result = await self.ml_service.categorize(transaction_description)
                ml_category = ml_result.get("category", "")
                ml_confidence = ml_result.get("confidence", 0.0)
            except Exception as e:
                logger.warning(f"ML categorization failed: {e}")
                ml_category = ""
                ml_confidence = 0.0
        
        ml_category = ml_category or ""
        ml_confidence = ml_confidence or 0.0
        
        # Determine agreement level
        agreement = self._check_agreement(ai_category, ml_category)
        
        # Decide final category
        final_category, used_override, explanation = self._decide_category(
            ai_category=ai_category,
            ai_confidence=ai_confidence,
            ml_category=ml_category,
            ml_confidence=ml_confidence,
            agreement=agreement,
        )
        
        return CrossValidationResult(
            ai_category=ai_category,
            ml_category=ml_category,
            ml_confidence=ml_confidence,
            agreement=agreement,
            final_category=final_category,
            used_ml_override=used_override,
            explanation=explanation,
        )
    
    def _check_agreement(self, ai_cat: str, ml_cat: str) -> AgreementLevel:
        """Check agreement level between categories."""
        ai_lower = ai_cat.lower().strip()
        ml_lower = ml_cat.lower().strip()
        
        # Exact match
        if ai_lower == ml_lower:
            return AgreementLevel.FULL
        
        # Check if same parent category
        ai_parent = CATEGORY_TO_PARENT.get(ai_lower)
        ml_parent = CATEGORY_TO_PARENT.get(ml_lower)
        
        if ai_parent and ml_parent and ai_parent == ml_parent:
            return AgreementLevel.PARTIAL
        
        # Check if one is parent of other
        if ai_lower in CATEGORY_HIERARCHY:
            if ml_lower in [c.lower() for c in CATEGORY_HIERARCHY.get(ai_lower, [])]:
                return AgreementLevel.PARTIAL
        if ml_lower in CATEGORY_HIERARCHY:
            if ai_lower in [c.lower() for c in CATEGORY_HIERARCHY.get(ml_lower, [])]:
                return AgreementLevel.PARTIAL
        
        return AgreementLevel.NONE
    
    def _decide_category(
        self,
        ai_category: str,
        ai_confidence: float,
        ml_category: str,
        ml_confidence: float,
        agreement: AgreementLevel,
    ) -> Tuple[str, bool, str]:
        """
        Decide final category based on AI/ML predictions.
        
        Returns:
            Tuple of (final_category, used_ml_override, explanation)
        """
        # Full agreement - use AI category (more specific naming)
        if agreement == AgreementLevel.FULL:
            return ai_category, False, "AI and ML agree"
        
        # Partial agreement - use more specific one
        if agreement == AgreementLevel.PARTIAL:
            # Prefer child category over parent
            if ai_category.lower() in CATEGORY_TO_PARENT:
                return ai_category, False, "AI provides more specific category"
            elif ml_category.lower() in CATEGORY_TO_PARENT:
                return ml_category, True, "ML provides more specific category"
            return ai_category, False, "Using AI category (partial agreement)"
        
        # Disagreement - use confidence and category preferences
        if ml_category in self.ML_PREFERRED_CATEGORIES:
            if ml_confidence >= self.ML_OVERRIDE_THRESHOLD:
                return ml_category, True, f"ML override (high confidence {ml_confidence:.2f})"
        
        if ai_category in self.AI_PREFERRED_CATEGORIES:
            return ai_category, False, "AI preferred for this category type"
        
        # Default: Use higher confidence
        if ml_confidence > ai_confidence and ml_confidence >= 0.8:
            return ml_category, True, f"ML higher confidence ({ml_confidence:.2f} > {ai_confidence:.2f})"
        
        return ai_category, False, "Using AI category (default)"


class FinancialRulesEngine:
    """
    Business rules for financial content validation.
    
    Applies domain-specific rules to ensure advice safety and accuracy.
    """
    
    # Maximum recommended percentages
    MAX_LIMITS = {
        "savings_rate": 70.0,       # Max % of income to save
        "emergency_months": 12,     # Max emergency fund months
        "debt_payment": 50.0,       # Max % of income to debt
        "investment_single": 25.0,  # Max % in single investment
        "discretionary": 30.0,      # Max discretionary spending %
    }
    
    # Minimum recommended values
    MIN_LIMITS = {
        "savings_rate": 10.0,       # Min savings rate %
        "emergency_months": 3,       # Min emergency fund months
        "retirement_contribution": 3.0,  # Min 401k contribution %
    }
    
    # Required disclaimers by topic
    REQUIRED_DISCLAIMERS = {
        "investment": "Investments carry risk. Past performance doesn't guarantee future results.",
        "tax": "Consult a tax professional for advice specific to your situation.",
        "debt": "Consider speaking with a financial advisor about debt management options.",
        "insurance": "Coverage needs vary. Consult an insurance professional.",
        "legal": "This is not legal advice. Consult an attorney for legal matters.",
    }
    
    # Topic detection patterns
    TOPIC_PATTERNS = {
        "investment": r"\b(?:invest|stock|bond|portfolio|401k|ira|mutual fund|etf)\b",
        "tax": r"\b(?:tax|deduct|irs|filing|refund|withhold)\b",
        "debt": r"\b(?:debt|loan|credit|borrow|mortgage|student loan)\b",
        "insurance": r"\b(?:insurance|coverage|policy|premium|claim)\b",
        "legal": r"\b(?:legal|lawsuit|sue|court|attorney|lawyer)\b",
    }
    
    def validate_advice(
        self,
        response: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Validate financial advice in response.
        
        Args:
            response: AI response text
            context: User financial context
            
        Returns:
            Dictionary with validation results
        """
        issues = []
        required_disclaimers = []
        
        # Check for topics requiring disclaimers
        for topic, pattern in self.TOPIC_PATTERNS.items():
            if re.search(pattern, response, re.IGNORECASE):
                disclaimer = self.REQUIRED_DISCLAIMERS.get(topic)
                if disclaimer and disclaimer.lower() not in response.lower():
                    required_disclaimers.append({
                        "topic": topic,
                        "disclaimer": disclaimer,
                    })
        
        # Check for unrealistic percentages
        percentage_matches = re.findall(
            r'(\d+(?:\.\d+)?)\s*%\s+(?:of\s+)?(?:your\s+)?(?:income|salary|earnings|budget)',
            response,
            re.IGNORECASE
        )
        for pct_str in percentage_matches:
            pct = float(pct_str)
            if pct > 100:
                issues.append({
                    "type": "impossible_percentage",
                    "message": f"{pct}% exceeds 100%",
                    "severity": "error",
                })
            elif pct > 80:
                issues.append({
                    "type": "extreme_percentage",
                    "message": f"{pct}% is extremely high",
                    "severity": "warning",
                })
        
        # Check for get-rich-quick language
        if re.search(r"get\s+rich\s+quick|easy\s+money|guaranteed\s+returns", response, re.IGNORECASE):
            issues.append({
                "type": "unrealistic_claims",
                "message": "Contains get-rich-quick language",
                "severity": "error",
            })
        
        return {
            "is_valid": len([i for i in issues if i["severity"] == "error"]) == 0,
            "issues": issues,
            "required_disclaimers": required_disclaimers,
        }
    
    def get_disclaimer_for_response(
        self,
        response: str,
    ) -> Optional[str]:
        """
        Get appropriate disclaimer for response content.
        
        Args:
            response: AI response text
            
        Returns:
            Disclaimer text or None
        """
        detected_topics = []
        
        for topic, pattern in self.TOPIC_PATTERNS.items():
            if re.search(pattern, response, re.IGNORECASE):
                detected_topics.append(topic)
        
        if not detected_topics:
            return None
        
        # Combine relevant disclaimers
        disclaimers = []
        for topic in detected_topics:
            if topic in self.REQUIRED_DISCLAIMERS:
                disclaimers.append(self.REQUIRED_DISCLAIMERS[topic])
        
        if disclaimers:
            return " ".join(disclaimers)
        
        return None


class AIValidationService:
    """
    Main validation service integrating all validation components.
    """
    
    def __init__(self, ml_service=None):
        """
        Initialize validation service.
        
        Args:
            ml_service: Optional ML categorization service
        """
        self.cross_validator = AIMLCrossValidator(ml_service)
        self.rules_engine = FinancialRulesEngine()
    
    async def validate_ai_response(
        self,
        response: str,
        mode: str,
        ai_confidence: float,
        parsed_data: Optional[Dict] = None,
        context: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Comprehensive validation of AI response.
        
        Args:
            response: AI response text
            mode: Response mode (chat, analyze, parse)
            ai_confidence: AI confidence score
            parsed_data: Parsed transaction data
            context: User context
            
        Returns:
            Validation result dictionary
        """
        result = {
            "is_valid": True,
            "confidence_adjusted": ai_confidence,
            "issues": [],
            "corrections": {},
            "disclaimers": [],
        }
        
        # Run rules validation
        rules_result = self.rules_engine.validate_advice(response, context)
        if not rules_result["is_valid"]:
            result["is_valid"] = False
        result["issues"].extend(rules_result["issues"])
        
        # Add required disclaimers
        for disc in rules_result["required_disclaimers"]:
            result["disclaimers"].append(disc["disclaimer"])
        
        # Cross-validate category if parse mode
        if mode == "parse" and parsed_data and "category" in parsed_data:
            description = parsed_data.get("merchant", "") or parsed_data.get("description", "")
            cv_result = await self.cross_validator.cross_validate(
                transaction_description=description,
                ai_category=parsed_data["category"],
                ai_confidence=ai_confidence,
            )
            
            result["cross_validation"] = cv_result.to_dict()
            
            if cv_result.used_ml_override:
                result["corrections"]["category"] = cv_result.final_category
                result["issues"].append({
                    "type": "category_override",
                    "message": cv_result.explanation,
                    "severity": "info",
                })
        
        # Add general disclaimer for financial content
        general_disclaimer = self.rules_engine.get_disclaimer_for_response(response)
        if general_disclaimer and general_disclaimer not in result["disclaimers"]:
            result["disclaimers"].append(general_disclaimer)
        
        return result


# Singleton instance
ai_validation_service = AIValidationService()


async def validate_ai_response(
    response: str,
    mode: str = "chat",
    ai_confidence: float = 0.95,
    parsed_data: Optional[Dict] = None,
    context: Optional[Dict] = None,
) -> Dict[str, Any]:
    """
    Convenience function for AI response validation.
    
    Args:
        response: AI response text
        mode: Response mode
        ai_confidence: AI confidence score
        parsed_data: Parsed data
        context: User context
        
    Returns:
        Validation result dictionary
    """
    return await ai_validation_service.validate_ai_response(
        response=response,
        mode=mode,
        ai_confidence=ai_confidence,
        parsed_data=parsed_data,
        context=context,
    )
