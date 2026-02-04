"""
Tests for the RAG (Retrieval-Augmented Generation) system.

Tests cover:
- MerchantDatabase lookup functionality
- MerchantNormalizer text processing
- RAGContextBuilder context building
- FeedbackCollector correction tracking
"""

import pytest
import json
from unittest.mock import patch, MagicMock

# Import the RAG components
from app.services.merchant_database import (
    MerchantDatabase,
    MerchantInfo,
)
from app.services.merchant_normalizer import (
    MerchantNormalizer,
)
from app.services.rag_context import (
    RAGContextBuilder,
)
from app.services.feedback_collector import (
    FeedbackCollector,
)


# ============================================================================
# MERCHANT DATABASE TESTS
# ============================================================================


class TestMerchantDatabase:
    """Tests for MerchantDatabase class."""

    @pytest.fixture
    def sample_merchant_data(self, tmp_path):
        """Create a sample merchants.json file."""
        data = {
            "version": "1.0.0",
            "categories": ["Groceries", "Fast Food", "Shopping", "Subscriptions"],
            "merchants": {
                "whole foods": {
                    "canonical_name": "Whole Foods Market",
                    "category": "Groceries",
                    "subcategory": "Organic Groceries",
                    "aliases": ["wholefds", "whole fds", "wholefoods"],
                    "is_recurring": False,
                    "typical_amounts": [50, 100, 200],
                },
                "mcdonalds": {
                    "canonical_name": "McDonald's",
                    "category": "Fast Food",
                    "subcategory": "Burgers",
                    "aliases": ["mcd", "mcds", "mcdonald's"],
                    "is_recurring": False,
                    "typical_amounts": [8, 15, 25],
                },
                "netflix": {
                    "canonical_name": "Netflix",
                    "category": "Subscriptions",
                    "subcategory": "Streaming",
                    "aliases": [],
                    "is_recurring": True,
                    "typical_amounts": [15.99],
                },
            },
            "patterns": [
                {"regex": "WHOLEFDS\\s*.*", "merchant": "whole foods", "category": "Groceries"},
                {"regex": "AMZN\\s*MKTP.*", "merchant": "amazon", "category": "Shopping"},
            ],
        }

        db_file = tmp_path / "merchants.json"
        with open(db_file, "w") as f:
            json.dump(data, f)

        return str(db_file)

    def test_load_database(self, sample_merchant_data):
        """Test loading the merchant database."""
        db = MerchantDatabase(sample_merchant_data)

        assert db._merchants
        assert len(db._merchants) == 3
        assert "whole foods" in db._merchants

    def test_exact_lookup(self, sample_merchant_data):
        """Test exact alias lookup."""
        db = MerchantDatabase(sample_merchant_data)

        # Test exact key match
        info = db.lookup("whole foods")
        assert info is not None
        assert info.category == "Groceries"
        assert info.canonical_name == "Whole Foods Market"
        assert info.match_type == "exact"
        assert info.match_score == 1.0

    def test_alias_lookup(self, sample_merchant_data):
        """Test lookup by alias."""
        db = MerchantDatabase(sample_merchant_data)

        info = db.lookup("wholefds")
        assert info is not None
        assert info.category == "Groceries"
        assert info.match_type == "exact"

    def test_pattern_lookup(self, sample_merchant_data):
        """Test regex pattern lookup."""
        db = MerchantDatabase(sample_merchant_data)

        info = db.lookup("WHOLEFDS 12345 AUSTIN TX")
        assert info is not None
        assert info.category == "Groceries"
        # Should match via pattern or partial

    def test_partial_lookup(self, sample_merchant_data):
        """Test partial matching."""
        db = MerchantDatabase(sample_merchant_data)

        info = db.lookup("mcdonalds 1234")
        assert info is not None
        assert info.category == "Fast Food"

    def test_fuzzy_lookup(self, sample_merchant_data):
        """Test fuzzy matching for typos."""
        db = MerchantDatabase(sample_merchant_data)

        # Close match to mcdonalds (typo that doesn't trigger partial match)
        info = db.lookup("macdonalds")
        if info:
            assert info.category == "Fast Food"
            assert info.match_type == "fuzzy"
            assert info.match_score < 1.0

    def test_lookup_not_found(self, sample_merchant_data):
        """Test lookup for unknown merchant."""
        db = MerchantDatabase(sample_merchant_data)

        info = db.lookup("completely unknown merchant xyz")
        assert info is None

    def test_get_category(self, sample_merchant_data):
        """Test convenience function for category lookup."""
        db = MerchantDatabase(sample_merchant_data)

        category = db.get_category("netflix")
        assert category == "Subscriptions"

    def test_add_merchant(self, sample_merchant_data):
        """Test adding a new merchant at runtime."""
        db = MerchantDatabase(sample_merchant_data)

        db.add_merchant(
            key="new store",
            canonical_name="New Store Inc",
            category="Shopping",
            aliases=["newstore", "new str"],
        )

        info = db.lookup("new store")
        assert info is not None
        assert info.category == "Shopping"

        # Also check alias works
        info = db.lookup("newstore")
        assert info is not None
        assert info.category == "Shopping"

    def test_get_all_categories(self, sample_merchant_data):
        """Test getting all categories."""
        db = MerchantDatabase(sample_merchant_data)

        categories = db.get_all_categories()
        assert "Groceries" in categories
        assert "Fast Food" in categories

    def test_is_valid_category(self, sample_merchant_data):
        """Test category validation."""
        db = MerchantDatabase(sample_merchant_data)

        assert db.is_valid_category("Groceries") is True
        assert db.is_valid_category("Invalid Category") is False

    def test_get_stats(self, sample_merchant_data):
        """Test database statistics."""
        db = MerchantDatabase(sample_merchant_data)

        stats = db.get_stats()
        assert stats["total_merchants"] == 3
        assert stats["total_patterns"] == 2
        assert stats["total_categories"] == 4

    def test_normalization(self, sample_merchant_data):
        """Test merchant string normalization."""
        db = MerchantDatabase(sample_merchant_data)

        normalized = db._normalize("WHOLEFDS 12345 AUSTIN TX")
        assert "12345" not in normalized
        assert "tx" not in normalized.split()[-1] or len(normalized) < 50

    def test_recurring_flag(self, sample_merchant_data):
        """Test recurring transaction flag."""
        db = MerchantDatabase(sample_merchant_data)

        info = db.lookup("netflix")
        assert info is not None
        assert info.is_recurring is True

        info = db.lookup("mcdonalds")
        assert info is not None
        assert info.is_recurring is False


# ============================================================================
# MERCHANT NORMALIZER TESTS
# ============================================================================


class TestMerchantNormalizer:
    """Tests for MerchantNormalizer class."""

    @pytest.fixture
    def normalizer(self):
        return MerchantNormalizer()

    def test_basic_normalization(self, normalizer):
        """Test basic text normalization."""
        result = normalizer.normalize("WHOLEFDS 12345 AUSTIN TX")

        assert result.merchant_name is not None
        assert len(result.merchant_name) > 0

    def test_payment_processor_extraction(self, normalizer):
        """Test Square/PayPal payment processor extraction."""
        result = normalizer.normalize("SQ *COFFEE SHOP")

        assert result.payment_processor == "Square"
        assert "coffee shop" in result.merchant_name.lower()

    def test_paypal_extraction(self, normalizer):
        """Test PayPal detection."""
        result = normalizer.normalize("PAYPAL *EBAY SELLER")

        assert result.payment_processor == "PayPal"

    def test_reference_number_removal(self, normalizer):
        """Test removal of reference/store numbers."""
        result = normalizer.normalize("MERCHANT #123456789 STORE TX")

        assert "123456789" not in result.merchant_name

    def test_abbreviation_expansion(self, normalizer):
        """Test common abbreviation expansion."""
        result = normalizer.normalize("WHOLEFDS")

        # Should expand or recognize as Whole Foods
        assert "whole" in result.merchant_name.lower() or "wholefds" in result.merchant_name.lower()

    def test_location_extraction(self, normalizer):
        """Test location extraction."""
        result = normalizer.normalize("STARBUCKS AUSTIN TX 78701")

        # Location should be extracted or cleaned
        assert result.merchant_name is not None

    def test_empty_input(self, normalizer):
        """Test handling of empty input."""
        result = normalizer.normalize("")

        assert result.merchant_name == ""

    def test_special_characters(self, normalizer):
        """Test handling of special characters."""
        result = normalizer.normalize("AMAZON.COM*AB12CD34")

        assert result.merchant_name is not None


# ============================================================================
# RAG CONTEXT BUILDER TESTS
# ============================================================================


class TestRAGContextBuilder:
    """Tests for RAGContextBuilder class."""

    @pytest.fixture
    def mock_merchant_db(self):
        """Create a mock merchant database."""
        with patch("app.services.rag_context.get_merchant_database") as mock:
            mock_db = MagicMock()
            mock_db.lookup.return_value = MerchantInfo(
                key="starbucks",
                canonical_name="Starbucks",
                category="Dining",
                subcategory="Coffee",
                aliases=["sbux"],
                is_recurring=False,
                match_type="exact",
                match_score=1.0,
            )
            mock.return_value = mock_db
            yield mock_db

    def test_build_parse_context(self, mock_merchant_db):
        """Test building context for parse mode."""
        builder = RAGContextBuilder()
        context = builder.build_parse_context("STARBUCKS 1234")

        assert context is not None
        assert context.mode == "parse"
        assert context.merchant_info is not None

    def test_build_chat_context(self):
        """Test building context for chat mode."""
        builder = RAGContextBuilder()
        context = builder.build_chat_context(
            query="How can I save money on groceries?", user_context={"monthly_income": 5000}
        )

        assert context is not None
        assert context.mode == "chat"

    def test_build_analyze_context(self):
        """Test building context for analysis mode."""
        builder = RAGContextBuilder()
        context = builder.build_analyze_context(
            transactions=[{"description": "Whole Foods", "amount": 50}],
            user_context={
                "spending": {"Groceries": 500, "Dining": 200},
                "monthly_income": 5000,
            },
        )

        assert context is not None
        assert context.mode == "analyze"

    def test_context_contains_guidelines(self):
        """Test that context includes financial guidelines."""
        builder = RAGContextBuilder()
        context = builder.build_chat_context("How can I budget better?")

        # Should have some guidelines
        assert context.financial_guidelines is not None or context.few_shot_examples

    def test_context_serialization(self):
        """Test that context can be serialized."""
        builder = RAGContextBuilder()
        context = builder.build_parse_context("WHOLEFDS 1234")

        # Should be convertible to dict/string for prompt injection
        context_dict = context.to_dict() if hasattr(context, "to_dict") else vars(context)
        assert isinstance(context_dict, dict)


# ============================================================================
# FEEDBACK COLLECTOR TESTS
# ============================================================================


class TestFeedbackCollector:
    """Tests for FeedbackCollector class."""

    @pytest.fixture
    def collector(self, tmp_path):
        """Create a feedback collector with temp storage."""
        corrections_path = str(tmp_path / "corrections.json")
        aggregates_path = str(tmp_path / "aggregates.json")

        return FeedbackCollector(
            corrections_path=corrections_path,
            aggregates_path=aggregates_path,
            auto_update_merchant_db=False,  # Disable for tests
            consensus_threshold=3,
        )

    @pytest.mark.asyncio
    async def test_record_correction(self, collector):
        """Test recording a single correction."""
        result = await collector.record_correction(
            user_id="user1",
            transaction_id="tx1",
            merchant_raw="WHOLEFDS 1234",
            original_category="Fast Food",
            corrected_category="Groceries",
        )

        assert result["status"] == "recorded"
        assert result["merchant_key"] is not None

    @pytest.mark.asyncio
    async def test_no_change_correction(self, collector):
        """Test that same category returns no_change."""
        result = await collector.record_correction(
            user_id="user1",
            transaction_id="tx1",
            merchant_raw="WHOLEFDS 1234",
            original_category="Groceries",
            corrected_category="Groceries",
        )

        assert result["status"] == "no_change"

    @pytest.mark.asyncio
    async def test_consensus_detection(self, collector):
        """Test that consensus is detected after threshold corrections."""
        merchant = "MYSTERY STORE 123"

        # Record 3 corrections (threshold)
        for i in range(3):
            result = await collector.record_correction(
                user_id=f"user{i}",
                transaction_id=f"tx{i}",
                merchant_raw=merchant,
                original_category="Other",
                corrected_category="Groceries",
            )

        # Last result should have consensus
        assert result["consensus_category"] == "Groceries"

    @pytest.mark.asyncio
    async def test_get_stats(self, collector):
        """Test statistics retrieval."""
        # Record some corrections
        await collector.record_correction(
            user_id="user1",
            transaction_id="tx1",
            merchant_raw="TEST MERCHANT",
            original_category="A",
            corrected_category="B",
        )

        stats = await collector.get_stats()

        assert stats["total_corrections"] == 1
        assert stats["unique_merchants_corrected"] == 1

    @pytest.mark.asyncio
    async def test_export_training_data(self, collector):
        """Test training data export."""
        # Record corrections
        for i in range(3):
            await collector.record_correction(
                user_id=f"user{i}",
                transaction_id=f"tx{i}",
                merchant_raw="TRAINING MERCHANT",
                original_category="Old",
                corrected_category="New",
            )

        training_data = await collector.export_training_data(min_corrections=1)

        assert len(training_data) >= 1
        assert "messages" in training_data[0]

    @pytest.mark.asyncio
    async def test_persistence(self, tmp_path):
        """Test that corrections persist to disk."""
        corrections_path = str(tmp_path / "corrections.json")
        aggregates_path = str(tmp_path / "aggregates.json")

        # Create collector and record correction
        collector1 = FeedbackCollector(
            corrections_path=corrections_path,
            aggregates_path=aggregates_path,
            auto_update_merchant_db=False,
        )

        await collector1.record_correction(
            user_id="user1",
            transaction_id="tx1",
            merchant_raw="PERSIST TEST",
            original_category="A",
            corrected_category="B",
        )

        # Force save
        await collector1._save_data()

        # Create new collector and check data loaded
        collector2 = FeedbackCollector(
            corrections_path=corrections_path,
            aggregates_path=aggregates_path,
            auto_update_merchant_db=False,
        )

        stats = await collector2.get_stats()
        assert stats["total_corrections"] >= 1


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


class TestRAGIntegration:
    """Integration tests for the full RAG pipeline."""

    @pytest.fixture
    def sample_db_path(self, tmp_path):
        """Create sample database for integration tests."""
        data = {
            "version": "1.0.0",
            "categories": [
                "Groceries",
                "Fast Food",
                "Shopping",
                "Subscriptions",
                "Transportation",
                "Utilities",
                "Healthcare",
            ],
            "merchants": {
                "whole foods": {
                    "canonical_name": "Whole Foods Market",
                    "category": "Groceries",
                    "aliases": ["wholefds"],
                    "is_recurring": False,
                },
                "uber": {
                    "canonical_name": "Uber",
                    "category": "Transportation",
                    "aliases": ["uber ride"],
                    "is_recurring": False,
                },
            },
            "patterns": [
                {"regex": "WHOLEFDS.*", "merchant": "whole foods", "category": "Groceries"}
            ],
        }

        db_file = tmp_path / "merchants.json"
        with open(db_file, "w") as f:
            json.dump(data, f)

        return str(db_file)

    def test_end_to_end_lookup(self, sample_db_path):
        """Test end-to-end transaction parsing."""
        # Initialize components
        db = MerchantDatabase(sample_db_path)
        normalizer = MerchantNormalizer()

        # Test transaction
        raw = "WHOLEFDS 12345 AUSTIN TX"

        # Normalize
        normalized = normalizer.normalize(raw)

        # Lookup
        info = db.lookup(normalized.merchant_name)

        assert info is not None
        assert info.category == "Groceries"

    def test_problematic_transactions(self, sample_db_path):
        """Test handling of problematic transaction formats."""
        db = MerchantDatabase(sample_db_path)
        normalizer = MerchantNormalizer()

        problematic = [
            "SQ *WHOLE FOODS",  # Square prefix
            "WHOLEFDS#1234",  # No space before number
            "UBER TRIP HELP.UBER.COM",  # With URL
        ]

        for raw in problematic:
            normalized = normalizer.normalize(raw)
            info = db.lookup(normalized.merchant_name)
            # Should handle gracefully (may or may not find)
            assert normalized.merchant_name is not None


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================


class TestPerformance:
    """Performance tests for RAG components."""

    @pytest.fixture
    def large_db(self, tmp_path):
        """Create a larger merchant database for perf tests."""
        merchants = {}
        for i in range(500):
            merchants[f"merchant_{i}"] = {
                "canonical_name": f"Merchant {i}",
                "category": ["Groceries", "Shopping", "Dining"][i % 3],
                "aliases": [f"m{i}", f"merch{i}"],
                "is_recurring": i % 10 == 0,
            }

        data = {
            "version": "1.0.0",
            "categories": ["Groceries", "Shopping", "Dining"],
            "merchants": merchants,
            "patterns": [],
        }

        db_file = tmp_path / "merchants.json"
        with open(db_file, "w") as f:
            json.dump(data, f)

        return str(db_file)

    def test_lookup_performance(self, large_db):
        """Test that lookup is fast even with large database."""
        import time

        db = MerchantDatabase(large_db)

        # Time 100 lookups
        start = time.time()
        for i in range(100):
            db.lookup(f"merchant_{i}")
        elapsed = time.time() - start

        # Should be very fast (< 1 second for 100 lookups)
        assert elapsed < 1.0, f"Lookup too slow: {elapsed:.2f}s for 100 lookups"

    def test_fuzzy_lookup_performance(self, large_db):
        """Test fuzzy matching performance."""
        import time

        db = MerchantDatabase(large_db)

        # Time 10 fuzzy lookups (more expensive)
        start = time.time()
        for i in range(10):
            db.lookup("unknwon mercahnt")  # Typos to trigger fuzzy
        elapsed = time.time() - start

        # Should still be reasonable
        assert elapsed < 5.0, f"Fuzzy lookup too slow: {elapsed:.2f}s for 10 lookups"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
