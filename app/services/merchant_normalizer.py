"""
Merchant Name Normalizer.

Advanced text processing to extract and normalize merchant names
from raw transaction descriptions. Handles common bank/card formats.
"""

import re
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


@dataclass
class NormalizedTransaction:
    """Result of transaction normalization."""

    original: str  # Original raw text
    merchant_name: str  # Extracted/cleaned merchant name
    amount: Optional[float] = None  # Extracted amount if found
    date: Optional[str] = None  # Extracted date if found
    location: Optional[str] = None  # Extracted location (city/state)
    reference: Optional[str] = None  # Reference/confirmation number
    payment_processor: Optional[str] = None  # Square, PayPal, etc.
    confidence: float = 1.0  # Confidence in extraction

    def to_dict(self) -> Dict:
        return {
            "original": self.original,
            "merchant_name": self.merchant_name,
            "amount": self.amount,
            "date": self.date,
            "location": self.location,
            "reference": self.reference,
            "payment_processor": self.payment_processor,
            "confidence": round(self.confidence, 3),
        }


class MerchantNormalizer:
    """
    Extract and normalize merchant names from transaction descriptions.

    Handles various formats from different banks and payment processors:
    - "WHOLEFDS 1234 AUSTIN TX" → "Whole Foods"
    - "SQ *COFFEE SHOP" → "Coffee Shop"
    - "AMZN MKTP US*AB12CD" → "Amazon"
    - "UBER   *TRIP HELP.UBER.COM" → "Uber"
    """

    # Payment processor prefixes to extract
    PAYMENT_PROCESSORS = {
        r"^SQ\s*\*\s*": "Square",
        r"^TST\s*\*\s*": "Toast",
        r"^PAYPAL\s*\*\s*": "PayPal",
        r"^STRIPE\s*\*?\s*": "Stripe",
        r"^PP\*": "PayPal",
        r"^GOFUNDME\s*\*?\s*": "GoFundMe",
    }

    # Known abbreviation mappings
    ABBREVIATIONS: Dict[str, str] = {
        "amzn": "amazon",
        "amzn mktp": "amazon",
        "wmt": "walmart",
        "tgt": "target",
        "sbux": "starbucks",
        "wholefds": "whole foods",
        "costco whse": "costco",
        "chick fil a": "chick-fil-a",
        "dd": "doordash",
        "uber trip": "uber",
        "lyft ride": "lyft",
        "mcd": "mcdonalds",
        "bk": "burger king",
        "jitb": "jack in the box",
        "cfa": "chick-fil-a",
        "qt": "quiktrip",
        "cvs/pharm": "cvs",
        "wawa": "wawa",
        "7-11": "7-eleven",
        "circlek": "circle k",
        "bp": "bp",
    }

    # Patterns to remove (noise)
    NOISE_PATTERNS = [
        r"\s*#\d+",  # Store numbers like #1234
        r"\s+\d{4,}$",  # Trailing numbers (4+ digits)
        r"\s+\d{5}(-\d{4})?$",  # ZIP codes
        r"\s+[A-Z]{2}$",  # State codes at end
        r"\s+\d{2}/\d{2}$",  # Dates like 01/15
        r"\s+\d{3}[-.]?\d{3}[-.]?\d{4}",  # Phone numbers
        r"\s+(INC|LLC|CORP|LTD|CO)\.?\s*$",  # Company suffixes
        r"\*[A-Z0-9]{5,}",  # Reference codes *AB12CD
        r"\s+HELP\..+\.COM",  # Help URLs
        r"\s+WWW\..+",  # Website URLs
        r"\s+HTTP.+",  # Full URLs
        r"\s+\d{1,2}:\d{2}\s*(AM|PM)?",  # Times
    ]

    # Amount patterns
    AMOUNT_PATTERN = re.compile(r"\$?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*$")

    # Date patterns
    DATE_PATTERNS = [
        (r"(\d{1,2}/\d{1,2}/\d{2,4})", "%m/%d/%Y"),
        (r"(\d{1,2}-\d{1,2}-\d{2,4})", "%m-%d-%Y"),
        (r"(\d{4}-\d{2}-\d{2})", "%Y-%m-%d"),
    ]

    # Location pattern (City, ST or City ST ZIP)
    LOCATION_PATTERN = re.compile(
        r"\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)(?:,\s*|\s+)([A-Z]{2})\s*(?:\d{5})?$", re.IGNORECASE
    )

    def __init__(self):
        self._compiled_noise = [re.compile(p, re.IGNORECASE) for p in self.NOISE_PATTERNS]
        self._compiled_processors = [
            (re.compile(p, re.IGNORECASE), name) for p, name in self.PAYMENT_PROCESSORS.items()
        ]

    def normalize(self, raw: str) -> NormalizedTransaction:
        """
        Normalize a raw transaction description.

        Args:
            raw: Raw transaction text from bank/card

        Returns:
            NormalizedTransaction with extracted components
        """
        if not raw:
            return NormalizedTransaction(
                original="",
                merchant_name="",
                confidence=0.0,
            )

        result = NormalizedTransaction(
            original=raw,
            merchant_name="",
        )

        text = raw.strip()

        # 1. Extract payment processor
        for pattern, processor in self._compiled_processors:
            match = pattern.match(text)
            if match:
                result.payment_processor = processor
                text = text[match.end() :].strip()
                break

        # 2. Extract amount from end if present
        amount_match = self.AMOUNT_PATTERN.search(text)
        if amount_match:
            try:
                result.amount = float(amount_match.group(1).replace(",", ""))
                text = text[: amount_match.start()].strip()
            except ValueError:
                pass

        # 3. Extract location
        location_match = self.LOCATION_PATTERN.search(text)
        if location_match:
            city = location_match.group(1)
            state = location_match.group(2)
            result.location = f"{city}, {state}".title()
            text = text[: location_match.start()].strip()

        # 4. Remove noise patterns
        for pattern in self._compiled_noise:
            text = pattern.sub("", text)

        # 5. Clean up multiple spaces
        text = re.sub(r"\s+", " ", text).strip()

        # 6. Apply abbreviation mappings
        text_lower = text.lower()
        for abbrev, full in self.ABBREVIATIONS.items():
            if text_lower.startswith(abbrev):
                text = full + text[len(abbrev) :]
                text_lower = text.lower()
                break

        # 7. Title case the result
        result.merchant_name = self._title_case(text)

        # 8. Calculate confidence based on how much we extracted
        result.confidence = self._calculate_confidence(raw, result)

        return result

    def _title_case(self, text: str) -> str:
        """
        Smart title case that handles special cases.
        """
        if not text:
            return ""

        # Words that should stay lowercase (unless first word)
        lowercase_words = {"a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for"}

        # Words that should stay uppercase
        uppercase_words = {
            "atm",
            "usps",
            "ups",
            "llc",
            "inc",
            "dba",
            "bp",
            "cvs",
            "kfc",
            "ihop",
            "amc",
        }

        words = text.lower().split()
        result = []

        for i, word in enumerate(words):
            if word in uppercase_words:
                result.append(word.upper())
            elif i == 0 or word not in lowercase_words:
                result.append(word.capitalize())
            else:
                result.append(word)

        return " ".join(result)

    def _calculate_confidence(
        self,
        raw: str,
        result: NormalizedTransaction,
    ) -> float:
        """Calculate confidence in the extraction."""
        confidence = 1.0

        # If merchant name is very short, lower confidence
        if len(result.merchant_name) < 3:
            confidence *= 0.5

        # If we extracted most components, higher confidence
        if result.payment_processor:
            confidence *= 0.95  # Processor known, good sign

        if result.location:
            confidence *= 1.0  # Location extracted, more structured

        # If original had lots of numbers, lower confidence
        num_count = sum(1 for c in raw if c.isdigit())
        if num_count > len(raw) * 0.4:
            confidence *= 0.7

        return min(1.0, confidence)

    def extract_merchant_and_amount(
        self,
        raw: str,
    ) -> Tuple[str, Optional[float]]:
        """
        Convenience method to get just merchant and amount.

        Returns:
            Tuple of (merchant_name, amount or None)
        """
        result = self.normalize(raw)
        return result.merchant_name, result.amount

    def extract_merchant(self, raw: str) -> str:
        """
        Convenience method to get just the merchant name.
        """
        return self.normalize(raw).merchant_name


# Singleton instance
_normalizer: Optional[MerchantNormalizer] = None


def get_normalizer() -> MerchantNormalizer:
    """Get the singleton MerchantNormalizer instance."""
    global _normalizer
    if _normalizer is None:
        _normalizer = MerchantNormalizer()
    return _normalizer


def normalize_merchant(raw: str) -> str:
    """
    Convenience function to normalize a merchant name.

    Args:
        raw: Raw transaction description

    Returns:
        Cleaned merchant name
    """
    return get_normalizer().extract_merchant(raw)


def normalize_transaction(raw: str) -> NormalizedTransaction:
    """
    Convenience function to fully normalize a transaction.

    Args:
        raw: Raw transaction description

    Returns:
        NormalizedTransaction with all extracted components
    """
    return get_normalizer().normalize(raw)
