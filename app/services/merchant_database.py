"""
Merchant Database Service.

Provides merchant lookup with pattern matching, alias resolution, and fuzzy matching.
Uses the comprehensive merchants.json database for accurate category assignments.
"""

import json
import os
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


@dataclass
class MerchantInfo:
    """Information about a merchant from the database."""

    key: str  # Database key (lowercase)
    canonical_name: str  # Display name
    category: str  # Primary category
    subcategory: Optional[str]  # Subcategory if available
    aliases: List[str]  # Known aliases
    is_recurring: bool  # Whether this is typically recurring
    typical_amounts: Optional[List[float]] = None  # Expected amounts if known
    match_type: str = "unknown"  # How the match was found
    match_score: float = 1.0  # Confidence in the match (0-1)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "key": self.key,
            "canonical_name": self.canonical_name,
            "category": self.category,
            "subcategory": self.subcategory,
            "is_recurring": self.is_recurring,
            "typical_amounts": self.typical_amounts,
            "match_type": self.match_type,
            "match_score": round(self.match_score, 3),
        }


class MerchantDatabase:
    """
    Production-ready merchant lookup service.

    Features:
    - Exact alias matching
    - Regex pattern matching for common formats
    - Fuzzy string matching for unknown merchants
    - Caching for performance

    Usage:
        db = MerchantDatabase()
        info = db.lookup("WHOLEFDS 12345 AUSTIN TX")
        print(info.category)  # "Groceries"
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the merchant database.

        Args:
            db_path: Path to merchants.json. Defaults to data/merchants.json
        """
        if db_path is None:
            # Find the data directory
            base_paths = [
                Path(__file__).parent.parent.parent / "data",  # From app/services
                Path(__file__).parent.parent / "data",  # From app
                Path.cwd() / "data",  # Current directory
            ]
            for base in base_paths:
                potential_path = base / "merchants.json"
                if potential_path.exists():
                    db_path = str(potential_path)
                    break

        if db_path is None or not os.path.exists(db_path):
            logger.warning(f"Merchant database not found at {db_path}, using empty database")
            self._merchants: Dict[str, Dict] = {}
            self._patterns: List[Tuple[re.Pattern, str, Optional[str]]] = []
            self._alias_index: Dict[str, str] = {}
            self._categories: List[str] = []
        else:
            self._load_database(db_path)

        self._exact_cache: Dict[str, Optional[MerchantInfo]] = {}

        logger.info(
            f"MerchantDatabase loaded: {len(self._merchants)} merchants, {len(self._patterns)} patterns"
        )

    def _load_database(self, db_path: str) -> None:
        """Load and index the merchant database."""
        with open(db_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self._merchants = data.get("merchants", {})
        self._categories = data.get("categories", [])

        # Compile regex patterns
        self._patterns = []
        for p in data.get("patterns", []):
            try:
                compiled = re.compile(p["regex"], re.IGNORECASE)
                note = p.get("note")
                self._patterns.append((compiled, p["merchant"], note))
            except re.error as e:
                logger.warning(f"Invalid regex pattern '{p['regex']}': {e}")

        # Build alias index for fast lookup
        self._alias_index = {}
        for key, merchant in self._merchants.items():
            # Add the key itself
            self._alias_index[key.lower()] = key
            # Add all aliases
            for alias in merchant.get("aliases", []):
                self._alias_index[alias.lower()] = key

    def lookup(self, raw_merchant: str) -> Optional[MerchantInfo]:
        """
        Find merchant info from a raw transaction description.

        Args:
            raw_merchant: Raw description like "WHOLEFDS 1234 AUSTIN TX"

        Returns:
            MerchantInfo if found, None if not matched
        """
        if not raw_merchant:
            return None

        # Normalize the input
        normalized = self._normalize(raw_merchant)

        # 1. Try exact alias match (fastest)
        result = self._lookup_exact(normalized)
        if result:
            result.match_type = "exact"
            result.match_score = 1.0
            return result

        # 2. Try regex pattern match
        result = self._lookup_pattern(normalized)
        if result:
            result.match_type = "pattern"
            result.match_score = 0.95
            return result

        # 3. Try partial alias match
        result = self._lookup_partial(normalized)
        if result:
            return result

        # 4. Try fuzzy match (slowest, last resort)
        result = self._lookup_fuzzy(normalized, threshold=0.80)
        if result:
            return result

        # Not found
        return None

    def _lookup_exact(self, normalized: str) -> Optional[MerchantInfo]:
        """Look up by exact alias match."""
        if normalized in self._exact_cache:
            return self._exact_cache[normalized]

        result = None
        if normalized in self._alias_index:
            key = self._alias_index[normalized]
            result = self._build_merchant_info(key)

        self._exact_cache[normalized] = result
        return result

    def _lookup_pattern(self, normalized: str) -> Optional[MerchantInfo]:
        """Look up by regex pattern match."""
        for pattern, merchant_key, note in self._patterns:
            if pattern.match(normalized):
                if merchant_key in self._merchants:
                    return self._build_merchant_info(merchant_key)
                # Handle special cases like Square payments
                if note:
                    logger.debug(f"Pattern matched with note: {note}")
        return None

    def _lookup_partial(self, normalized: str) -> Optional[MerchantInfo]:
        """Look up by partial alias match."""
        # Check if normalized starts with or contains a known alias
        for alias, key in self._alias_index.items():
            if len(alias) >= 3:  # Only match aliases of 3+ chars
                if normalized.startswith(alias) or alias in normalized:
                    info = self._build_merchant_info(key)
                    if info:
                        info.match_type = "partial"
                        info.match_score = 0.85
                        return info
        return None

    def _lookup_fuzzy(self, normalized: str, threshold: float = 0.80) -> Optional[MerchantInfo]:
        """
        Look up by fuzzy string matching.

        Uses Levenshtein-like ratio scoring from difflib.
        """
        best_match = None
        best_score = threshold

        # Only compare against merchant names (not all aliases - too slow)
        for key in self._merchants.keys():
            matcher = SequenceMatcher(None, normalized, key)
            # Optimization: check upper bounds before expensive ratio calculation
            if matcher.real_quick_ratio() <= best_score:
                continue
            if matcher.quick_ratio() <= best_score:
                continue

            score = matcher.ratio()
            if score > best_score:
                best_score = score
                best_match = key

        if best_match:
            info = self._build_merchant_info(best_match)
            if info:
                info.match_type = "fuzzy"
                info.match_score = best_score
                return info

        return None

    def _build_merchant_info(self, key: str) -> Optional[MerchantInfo]:
        """Build a MerchantInfo object from database entry."""
        if key not in self._merchants:
            return None

        m = self._merchants[key]
        return MerchantInfo(
            key=key,
            canonical_name=m.get("canonical_name", key.title()),
            category=m.get("category", "Other"),
            subcategory=m.get("subcategory"),
            aliases=m.get("aliases", []),
            is_recurring=m.get("is_recurring", False),
            typical_amounts=m.get("typical_amounts"),
        )

    def _normalize(self, text: str) -> str:
        """
        Normalize a merchant string for matching.

        Removes:
        - Store/reference numbers
        - City/state/zip
        - Phone numbers
        - Common suffixes (INC, LLC, etc.)
        """
        if not text:
            return ""

        # Convert to lowercase
        text = text.lower().strip()

        # Remove common payment processor prefixes
        text = re.sub(r"^(sq\s*\*|tst\s*\*|paypal\s*\*)", "", text)

        # Remove reference codes like *AB12CD
        text = re.sub(r"\*[a-z0-9]+", "", text, flags=re.I)

        # Remove store/reference numbers (4+ digits at end)
        text = re.sub(r"\s*#?\d{4,}.*$", "", text)

        # Remove phone numbers
        text = re.sub(r"\s*\d{3}[-.\s]?\d{3}[-.\s]?\d{4}", "", text)

        # Remove city/state/zip patterns
        text = re.sub(r"\s+[a-z]{2}\s+\d{5}(-\d{4})?$", "", text, flags=re.I)
        text = re.sub(r"\s+[a-z]{2}$", "", text, flags=re.I)

        # Remove company suffixes
        text = re.sub(r"\s+(inc|llc|corp|ltd|co|company)\.?\s*$", "", text, flags=re.I)

        # Clean up whitespace
        text = re.sub(r"\s+", " ", text).strip()

        return text

    def get_category(self, raw_merchant: str) -> Optional[str]:
        """
        Get just the category for a merchant.

        Convenience method for simple category lookups.
        """
        info = self.lookup(raw_merchant)
        return info.category if info else None

    def get_all_categories(self) -> List[str]:
        """Get list of all valid categories."""
        return self._categories.copy()

    def is_valid_category(self, category: str) -> bool:
        """Check if a category is in our valid list."""
        return category in self._categories

    def add_merchant(
        self,
        key: str,
        canonical_name: str,
        category: str,
        aliases: Optional[List[str]] = None,
        **kwargs,
    ) -> None:
        """
        Add a merchant to the runtime database.

        Note: This does not persist to disk. Use for user-provided corrections.
        """
        key = key.lower()
        self._merchants[key] = {
            "canonical_name": canonical_name,
            "category": category,
            "aliases": aliases or [],
            **kwargs,
        }
        # Update alias index
        self._alias_index[key] = key
        for alias in aliases or []:
            self._alias_index[alias.lower()] = key

        # Clear the exact match cache
        self._exact_cache.clear()

        logger.info(f"Added merchant: {key} -> {category}")

    def get_stats(self) -> Dict[str, int]:
        """Get database statistics."""
        return {
            "total_merchants": len(self._merchants),
            "total_aliases": len(self._alias_index),
            "total_patterns": len(self._patterns),
            "total_categories": len(self._categories),
        }


# Singleton instance
_merchant_db: Optional[MerchantDatabase] = None


def get_merchant_database() -> MerchantDatabase:
    """Get the singleton MerchantDatabase instance."""
    global _merchant_db
    if _merchant_db is None:
        _merchant_db = MerchantDatabase()
    return _merchant_db


def lookup_merchant(raw_merchant: str) -> Optional[MerchantInfo]:
    """
    Convenience function to look up a merchant.

    Args:
        raw_merchant: Raw transaction description

    Returns:
        MerchantInfo if found
    """
    return get_merchant_database().lookup(raw_merchant)


def get_category(raw_merchant: str) -> Optional[str]:
    """
    Convenience function to get just the category.

    Args:
        raw_merchant: Raw transaction description

    Returns:
        Category string if found
    """
    return get_merchant_database().get_category(raw_merchant)
