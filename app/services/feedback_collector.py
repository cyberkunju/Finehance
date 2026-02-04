"""
User Feedback Collection Service.

Collects and manages user corrections for continuous improvement.
Category corrections are used to:
1. Auto-update the merchant database when consensus is reached
2. Generate training data for future model fine-tuning
3. Track accuracy metrics over time
"""

import asyncio
import json
import os
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
import logging

logger = logging.getLogger(__name__)


@dataclass
class CategoryCorrection:
    """A single category correction record."""
    
    user_id: str
    transaction_id: str
    merchant_raw: str
    merchant_normalized: Optional[str]
    original_category: str
    corrected_category: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    source: str = "user"  # user, ai, rule
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "transaction_id": self.transaction_id,
            "merchant_raw": self.merchant_raw,
            "merchant_normalized": self.merchant_normalized,
            "original_category": self.original_category,
            "corrected_category": self.corrected_category,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "CategoryCorrection":
        return cls(
            user_id=data["user_id"],
            transaction_id=data["transaction_id"],
            merchant_raw=data["merchant_raw"],
            merchant_normalized=data.get("merchant_normalized"),
            original_category=data["original_category"],
            corrected_category=data["corrected_category"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            source=data.get("source", "user"),
        )


@dataclass
class MerchantCorrectionAgg:
    """Aggregated corrections for a merchant."""
    
    merchant_key: str
    corrections: Dict[str, int] = field(default_factory=dict)  # category -> count
    total_corrections: int = 0
    last_updated: datetime = field(default_factory=datetime.utcnow)
    
    def add_correction(self, corrected_category: str):
        """Add a correction to the aggregation."""
        self.corrections[corrected_category] = self.corrections.get(corrected_category, 0) + 1
        self.total_corrections += 1
        self.last_updated = datetime.utcnow()
    
    def get_consensus(self, min_count: int = 3) -> Optional[str]:
        """
        Get the consensus category if one exists.
        
        Returns category if it has >= min_count corrections,
        and represents majority of corrections.
        """
        if not self.corrections:
            return None
        
        top_category = max(self.corrections, key=self.corrections.get)
        top_count = self.corrections[top_category]
        
        # Need minimum count and majority
        if top_count >= min_count and top_count > self.total_corrections / 2:
            return top_category
        
        return None


class FeedbackCollector:
    """
    Collect and manage user feedback for continuous improvement.
    
    Features:
    - Store corrections in-memory and persist to JSON
    - Aggregate corrections per merchant
    - Auto-update merchant database on consensus
    - Export data for training
    
    Usage:
        collector = FeedbackCollector()
        await collector.record_correction(
            user_id="user123",
            transaction_id="tx456",
            merchant_raw="WHOLEFDS 1234",
            original_category="Fast Food",
            corrected_category="Groceries",
        )
    """
    
    # Minimum corrections needed to update merchant database
    CONSENSUS_THRESHOLD = 3
    
    # File paths for persistence
    DEFAULT_CORRECTIONS_PATH = "data/feedback/corrections.json"
    DEFAULT_AGGREGATES_PATH = "data/feedback/aggregates.json"
    
    def __init__(
        self,
        corrections_path: Optional[str] = None,
        aggregates_path: Optional[str] = None,
        auto_update_merchant_db: bool = True,
        consensus_threshold: int = 3,
    ):
        """
        Initialize the feedback collector.
        
        Args:
            corrections_path: Path to store corrections JSON
            aggregates_path: Path to store aggregates JSON
            auto_update_merchant_db: Whether to auto-update DB on consensus
            consensus_threshold: Minimum corrections for auto-update
        """
        self.corrections_path = corrections_path or self.DEFAULT_CORRECTIONS_PATH
        self.aggregates_path = aggregates_path or self.DEFAULT_AGGREGATES_PATH
        self.auto_update_merchant_db = auto_update_merchant_db
        self.consensus_threshold = consensus_threshold
        
        # In-memory storage
        self._corrections: List[CategoryCorrection] = []
        self._aggregates: Dict[str, MerchantCorrectionAgg] = {}
        self._lock = asyncio.Lock()
        
        # Statistics
        self._stats = {
            "total_corrections": 0,
            "auto_updates_made": 0,
            "unique_merchants_corrected": 0,
        }
        
        # Load persisted data
        self._load_data()
    
    def _load_data(self):
        """Load corrections from disk."""
        # Load corrections
        try:
            path = Path(self.corrections_path)
            if path.exists():
                with open(path, 'r') as f:
                    data = json.load(f)
                    self._corrections = [
                        CategoryCorrection.from_dict(c) 
                        for c in data.get("corrections", [])
                    ]
                    self._stats = data.get("stats", self._stats)
                logger.info(f"Loaded {len(self._corrections)} corrections from {path}")
        except Exception as e:
            logger.warning(f"Failed to load corrections: {e}")
        
        # Load aggregates
        try:
            path = Path(self.aggregates_path)
            if path.exists():
                with open(path, 'r') as f:
                    data = json.load(f)
                    for key, agg in data.get("aggregates", {}).items():
                        self._aggregates[key] = MerchantCorrectionAgg(
                            merchant_key=key,
                            corrections=agg.get("corrections", {}),
                            total_corrections=agg.get("total_corrections", 0),
                            last_updated=datetime.fromisoformat(agg.get("last_updated", datetime.utcnow().isoformat())),
                        )
                logger.info(f"Loaded {len(self._aggregates)} merchant aggregates")
        except Exception as e:
            logger.warning(f"Failed to load aggregates: {e}")
    
    async def _save_data(self):
        """Persist corrections to disk."""
        async with self._lock:
            try:
                # Ensure directory exists
                corrections_dir = Path(self.corrections_path).parent
                corrections_dir.mkdir(parents=True, exist_ok=True)
                
                # Save corrections
                with open(self.corrections_path, 'w') as f:
                    json.dump({
                        "corrections": [c.to_dict() for c in self._corrections[-10000:]],  # Keep last 10k
                        "stats": self._stats,
                        "last_saved": datetime.utcnow().isoformat(),
                    }, f, indent=2)
                
                # Save aggregates
                aggregates_dir = Path(self.aggregates_path).parent
                aggregates_dir.mkdir(parents=True, exist_ok=True)
                
                with open(self.aggregates_path, 'w') as f:
                    json.dump({
                        "aggregates": {
                            key: {
                                "corrections": agg.corrections,
                                "total_corrections": agg.total_corrections,
                                "last_updated": agg.last_updated.isoformat(),
                            }
                            for key, agg in self._aggregates.items()
                        },
                        "last_saved": datetime.utcnow().isoformat(),
                    }, f, indent=2)
                    
            except Exception as e:
                logger.error(f"Failed to save feedback data: {e}")
    
    def _normalize_merchant_key(self, merchant_raw: str) -> str:
        """Normalize merchant name to a key for aggregation."""
        import re
        # Remove numbers, special chars, lowercase, strip
        key = re.sub(r'[^a-zA-Z\s]', '', merchant_raw)
        key = ' '.join(key.lower().split())
        # Take first 2-3 words
        words = key.split()[:3]
        return ' '.join(words)
    
    async def record_correction(
        self,
        user_id: str,
        transaction_id: str,
        merchant_raw: str,
        original_category: str,
        corrected_category: str,
        merchant_normalized: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Record a category correction from a user.
        
        Args:
            user_id: ID of the user making correction
            transaction_id: ID of the transaction
            merchant_raw: Raw merchant description
            original_category: The AI-assigned category
            corrected_category: The user's corrected category
            merchant_normalized: Normalized merchant name if available
            
        Returns:
            Dict with correction status and any auto-updates made
        """
        if original_category == corrected_category:
            return {"status": "no_change", "message": "Categories are the same"}
        
        # Create correction record
        correction = CategoryCorrection(
            user_id=user_id,
            transaction_id=transaction_id,
            merchant_raw=merchant_raw,
            merchant_normalized=merchant_normalized,
            original_category=original_category,
            corrected_category=corrected_category,
        )
        
        result = {
            "status": "recorded",
            "merchant_key": None,
            "auto_updated": False,
            "consensus_category": None,
        }
        
        async with self._lock:
            # Store correction
            self._corrections.append(correction)
            self._stats["total_corrections"] += 1
            
            # Aggregate by merchant
            merchant_key = self._normalize_merchant_key(merchant_raw)
            result["merchant_key"] = merchant_key
            
            if merchant_key not in self._aggregates:
                self._aggregates[merchant_key] = MerchantCorrectionAgg(
                    merchant_key=merchant_key
                )
                self._stats["unique_merchants_corrected"] += 1
            
            self._aggregates[merchant_key].add_correction(corrected_category)
            
            # Check for consensus
            consensus = self._aggregates[merchant_key].get_consensus(
                self.consensus_threshold
            )
            
            if consensus:
                result["consensus_category"] = consensus
                
                # Auto-update merchant database if enabled
                if self.auto_update_merchant_db:
                    updated = await self._update_merchant_db(
                        merchant_key, 
                        consensus,
                        merchant_normalized,
                    )
                    result["auto_updated"] = updated
                    if updated:
                        self._stats["auto_updates_made"] += 1
        
        # Save asynchronously
        asyncio.create_task(self._save_data())
        
        logger.info(
            f"Recorded correction: {merchant_raw} ({original_category} -> {corrected_category})",
            extra=result,
        )
        
        return result
    
    async def _update_merchant_db(
        self,
        merchant_key: str,
        category: str,
        merchant_normalized: Optional[str],
    ) -> bool:
        """Update the merchant database with consensus category."""
        try:
            from app.services.merchant_database import get_merchant_database
            
            merchant_db = get_merchant_database()
            
            # Add/update merchant in runtime database
            merchant_db.add_merchant(
                key=merchant_key,
                canonical_name=merchant_normalized or merchant_key.title(),
                category=category,
                aliases=[merchant_key],
            )
            
            logger.info(
                f"Auto-updated merchant DB: {merchant_key} -> {category}",
                merchant_normalized=merchant_normalized,
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to auto-update merchant DB: {e}")
            return False
    
    async def get_corrections_for_merchant(
        self,
        merchant_raw: str,
    ) -> List[CategoryCorrection]:
        """Get all corrections for a merchant."""
        merchant_key = self._normalize_merchant_key(merchant_raw)
        
        return [
            c for c in self._corrections
            if self._normalize_merchant_key(c.merchant_raw) == merchant_key
        ]
    
    async def get_recent_corrections(
        self,
        limit: int = 100,
        since: Optional[datetime] = None,
    ) -> List[CategoryCorrection]:
        """Get recent corrections."""
        corrections = self._corrections
        
        if since:
            corrections = [c for c in corrections if c.timestamp >= since]
        
        return sorted(
            corrections,
            key=lambda c: c.timestamp,
            reverse=True,
        )[:limit]
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get feedback collection statistics."""
        return {
            **self._stats,
            "aggregates_count": len(self._aggregates),
            "pending_consensus": sum(
                1 for agg in self._aggregates.values()
                if agg.total_corrections > 0 and agg.get_consensus(self.consensus_threshold) is None
            ),
            "has_consensus": sum(
                1 for agg in self._aggregates.values()
                if agg.get_consensus(self.consensus_threshold) is not None
            ),
        }
    
    async def export_training_data(
        self,
        min_corrections: int = 1,
        format: str = "chatml",
    ) -> List[Dict]:
        """
        Export corrections as training data.
        
        Args:
            min_corrections: Minimum corrections per merchant to include
            format: Output format ("chatml" or "simple")
            
        Returns:
            List of training examples
        """
        training_data = []
        
        # Group corrections by merchant and use most common category
        merchant_categories = defaultdict(lambda: defaultdict(int))
        merchant_examples = defaultdict(list)
        
        for correction in self._corrections:
            key = self._normalize_merchant_key(correction.merchant_raw)
            merchant_categories[key][correction.corrected_category] += 1
            merchant_examples[key].append(correction.merchant_raw)
        
        for merchant_key, categories in merchant_categories.items():
            total = sum(categories.values())
            if total < min_corrections:
                continue
            
            # Get most common category
            best_category = max(categories, key=categories.get)
            
            # Use the most common raw description as example
            raw_examples = merchant_examples[merchant_key]
            example_raw = max(set(raw_examples), key=raw_examples.count)
            
            if format == "chatml":
                training_data.append({
                    "messages": [
                        {"role": "system", "content": "You are a transaction parser. Return JSON with category."},
                        {"role": "user", "content": f"Parse this transaction: {example_raw}"},
                        {"role": "assistant", "content": json.dumps({
                            "merchant": merchant_key.title(),
                            "category": best_category,
                            "confidence": 0.95,
                        })},
                    ],
                    "metadata": {
                        "corrections_count": total,
                        "agreement_ratio": categories[best_category] / total,
                    },
                })
            else:
                training_data.append({
                    "input": example_raw,
                    "output": best_category,
                    "merchant": merchant_key,
                    "corrections_count": total,
                })
        
        logger.info(
            f"Exported {len(training_data)} training examples",
            min_corrections=min_corrections,
            format=format,
        )
        
        return training_data
    
    async def save_training_export(
        self,
        output_path: str = "data/feedback/training_export.json",
        min_corrections: int = 1,
    ) -> str:
        """Export and save training data to file."""
        training_data = await self.export_training_data(min_corrections)
        
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output, 'w') as f:
            json.dump({
                "examples": training_data,
                "exported_at": datetime.utcnow().isoformat(),
                "total_examples": len(training_data),
                "min_corrections": min_corrections,
            }, f, indent=2)
        
        logger.info(f"Saved training export to {output_path}")
        return str(output)


# Singleton instance
_feedback_collector: Optional[FeedbackCollector] = None


def get_feedback_collector() -> FeedbackCollector:
    """Get the singleton FeedbackCollector instance."""
    global _feedback_collector
    if _feedback_collector is None:
        _feedback_collector = FeedbackCollector()
    return _feedback_collector


async def record_category_correction(
    user_id: str,
    transaction_id: str,
    merchant_raw: str,
    original_category: str,
    corrected_category: str,
    merchant_normalized: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Convenience function to record a category correction.
    
    This is the main entry point for the feedback collection system.
    """
    collector = get_feedback_collector()
    return await collector.record_correction(
        user_id=user_id,
        transaction_id=transaction_id,
        merchant_raw=merchant_raw,
        original_category=original_category,
        corrected_category=corrected_category,
        merchant_normalized=merchant_normalized,
    )
