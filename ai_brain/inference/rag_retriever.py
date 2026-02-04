"""
🔍 RAG (Retrieval Augmented Generation) for Financial Brain

Retrieves relevant user financial data to provide context
for the AI Brain's responses.

Uses vector embeddings for semantic search on transactions,
combined with structured data retrieval for budgets, goals, etc.
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from decimal import Decimal
import logging

import numpy as np

logger = logging.getLogger(__name__)


class FinancialRAG:
    """
    Retrieval Augmented Generation for Financial Data
    
    Retrieves and formats relevant financial context for the AI Brain.
    """
    
    def __init__(self, db_connection=None):
        """
        Initialize the RAG system.
        
        Args:
            db_connection: Database connection (or None for mock data)
        """
        self.db = db_connection
        self.embedding_model = None
        self.transaction_index = None
        
    def load_embedding_model(self):
        """Load the sentence embedding model."""
        try:
            from sentence_transformers import SentenceTransformer
            
            # Use a small, fast model
            self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("Embedding model loaded")
            
        except ImportError:
            logger.warning("sentence-transformers not installed. Semantic search disabled.")
    
    async def get_context(
        self,
        user_id: str,
        query: str,
        max_transactions: int = 10,
    ) -> Dict[str, Any]:
        """
        Get relevant financial context for a user query.
        
        Args:
            user_id: User ID
            query: User's query
            max_transactions: Maximum transactions to include
            
        Returns:
            Context dictionary with relevant financial data
        """
        context = {}
        
        # Get user profile
        profile = await self._get_user_profile(user_id)
        if profile:
            context["profile"] = profile
        
        # Get spending summary
        spending = await self._get_spending_summary(user_id)
        if spending:
            context["spending"] = spending
            context["monthly_income"] = spending.get("income", 0)
        
        # Get relevant transactions (semantically similar to query)
        transactions = await self._get_relevant_transactions(user_id, query, max_transactions)
        if transactions:
            context["recent_transactions"] = transactions
        
        # Get budgets
        budgets = await self._get_budgets(user_id)
        if budgets:
            context["budgets"] = budgets
        
        # Get goals
        goals = await self._get_goals(user_id)
        if goals:
            context["goals"] = goals
        
        # Get subscription info
        subscriptions = await self._detect_subscriptions(user_id)
        if subscriptions:
            context["subscriptions"] = len(subscriptions)
            context["subscription_cost"] = sum(s["amount"] for s in subscriptions)
            context["subscription_list"] = subscriptions
        
        return context
    
    async def _get_user_profile(self, user_id: str) -> Optional[Dict]:
        """Get user profile information."""
        if self.db:
            # Real DB query
            pass
        
        # Mock data for testing
        return {
            "name": "User",
            "member_since": "2024",
        }
    
    async def _get_spending_summary(self, user_id: str) -> Dict:
        """Get spending summary by category."""
        if self.db:
            # Real DB query
            pass
        
        # Mock data for testing
        return {
            "income": 5000,
            "total_spent": 3800,
            "by_category": {
                "Food & Dining": 850,
                "Transportation": 220,
                "Shopping & Retail": 450,
                "Entertainment & Recreation": 180,
                "Utilities & Services": 350,
                "Healthcare & Medical": 120,
            },
            "period": "current_month",
        }
    
    async def _get_relevant_transactions(
        self,
        user_id: str,
        query: str,
        max_count: int,
    ) -> List[Dict]:
        """Get transactions relevant to the query."""
        # Get recent transactions
        transactions = await self._get_recent_transactions(user_id, days=30)
        
        if not transactions:
            return []
        
        # If no embedding model, return most recent
        if not self.embedding_model:
            return transactions[:max_count]
        
        # Semantic search
        query_embedding = self.embedding_model.encode([query])[0]
        
        # Get embeddings for transaction descriptions
        descriptions = [t["description"] for t in transactions]
        desc_embeddings = self.embedding_model.encode(descriptions)
        
        # Calculate similarity scores
        scores = np.dot(desc_embeddings, query_embedding)
        
        # Sort by relevance
        sorted_indices = np.argsort(scores)[::-1]
        
        return [transactions[i] for i in sorted_indices[:max_count]]
    
    async def _get_recent_transactions(
        self,
        user_id: str,
        days: int = 30,
    ) -> List[Dict]:
        """Get recent transactions."""
        if self.db:
            # Real DB query
            pass
        
        # Mock data for testing
        return [
            {"date": "2026-01-28", "description": "STARBUCKS STORE 12345", "amount": 7.50, "category": "Food & Dining"},
            {"date": "2026-01-27", "description": "AMAZON.COM*Z1234ABC", "amount": 45.99, "category": "Shopping & Retail"},
            {"date": "2026-01-27", "description": "UBER *TRIP X9Y8Z7", "amount": 22.50, "category": "Transportation"},
            {"date": "2026-01-26", "description": "NETFLIX.COM", "amount": 15.99, "category": "Entertainment & Recreation"},
            {"date": "2026-01-26", "description": "WHOLE FOODS MARKET", "amount": 89.75, "category": "Food & Dining"},
            {"date": "2026-01-25", "description": "SHELL GAS STATION", "amount": 52.00, "category": "Transportation"},
            {"date": "2026-01-25", "description": "CVS PHARMACY", "amount": 28.99, "category": "Healthcare & Medical"},
            {"date": "2026-01-24", "description": "CHIPOTLE MEXICAN GRILL", "amount": 14.50, "category": "Food & Dining"},
            {"date": "2026-01-24", "description": "SPOTIFY PREMIUM", "amount": 10.99, "category": "Entertainment & Recreation"},
            {"date": "2026-01-23", "description": "TARGET STORE 4567", "amount": 67.23, "category": "Shopping & Retail"},
        ]
    
    async def _get_budgets(self, user_id: str) -> List[Dict]:
        """Get user budgets."""
        if self.db:
            # Real DB query
            pass
        
        # Mock data
        return [
            {"category": "Food & Dining", "limit": 800, "spent": 850, "remaining": -50},
            {"category": "Shopping & Retail", "limit": 400, "spent": 450, "remaining": -50},
            {"category": "Entertainment & Recreation", "limit": 200, "spent": 180, "remaining": 20},
            {"category": "Transportation", "limit": 300, "spent": 220, "remaining": 80},
        ]
    
    async def _get_goals(self, user_id: str) -> List[Dict]:
        """Get user financial goals."""
        if self.db:
            # Real DB query
            pass
        
        # Mock data
        return [
            {
                "name": "Emergency Fund",
                "target": 10000,
                "current": 3500,
                "deadline": "2026-06-01",
                "monthly_contribution": 500,
            },
            {
                "name": "Vacation to Japan",
                "target": 5000,
                "current": 1800,
                "deadline": "2026-09-01",
                "monthly_contribution": 400,
            },
        ]
    
    async def _detect_subscriptions(self, user_id: str) -> List[Dict]:
        """Detect recurring subscriptions from transaction history."""
        if self.db:
            # Real detection logic
            pass
        
        # Mock data
        return [
            {"merchant": "Netflix", "amount": 15.99, "frequency": "monthly", "last_charge": "2026-01-26"},
            {"merchant": "Spotify", "amount": 10.99, "frequency": "monthly", "last_charge": "2026-01-24"},
            {"merchant": "Amazon Prime", "amount": 14.99, "frequency": "monthly", "last_charge": "2026-01-15"},
            {"merchant": "Gym Membership", "amount": 49.99, "frequency": "monthly", "last_charge": "2026-01-01"},
            {"merchant": "HBO Max", "amount": 15.99, "frequency": "monthly", "last_charge": "2026-01-10"},
            {"merchant": "Apple iCloud", "amount": 2.99, "frequency": "monthly", "last_charge": "2026-01-20"},
            {"merchant": "YouTube Premium", "amount": 13.99, "frequency": "monthly", "last_charge": "2026-01-18"},
        ]
    
    def format_context(self, context: Dict) -> str:
        """
        Format context as a string for the AI prompt.
        
        Args:
            context: Context dictionary
            
        Returns:
            Formatted string
        """
        parts = []
        
        # Income and spending summary
        if "spending" in context:
            spending = context["spending"]
            parts.append(f"Monthly Income: ${spending.get('income', 0):,}")
            parts.append(f"Total Spent This Month: ${spending.get('total_spent', 0):,}")
            
            if "by_category" in spending:
                parts.append("\nSpending by Category:")
                for cat, amount in spending["by_category"].items():
                    parts.append(f"  - {cat}: ${amount:,.2f}")
        
        # Budgets
        if "budgets" in context:
            parts.append("\nBudget Status:")
            for budget in context["budgets"]:
                status = "⚠️ OVER" if budget["remaining"] < 0 else "✅"
                parts.append(
                    f"  - {budget['category']}: ${budget['spent']:.0f} / ${budget['limit']:.0f} {status}"
                )
        
        # Goals
        if "goals" in context:
            parts.append("\nFinancial Goals:")
            for goal in context["goals"]:
                progress = (goal["current"] / goal["target"]) * 100
                parts.append(
                    f"  - {goal['name']}: ${goal['current']:,} / ${goal['target']:,} ({progress:.0f}%)"
                )
        
        # Subscriptions
        if "subscriptions" in context:
            parts.append(f"\nActive Subscriptions: {context['subscriptions']} (${context['subscription_cost']:.2f}/month)")
        
        # Recent transactions
        if "recent_transactions" in context:
            parts.append("\nRecent Transactions:")
            for tx in context["recent_transactions"][:5]:
                parts.append(
                    f"  - {tx['date']}: {tx['description'][:30]}: ${tx['amount']:.2f} ({tx['category']})"
                )
        
        return "\n".join(parts)


class DatabaseRAG(FinancialRAG):
    """RAG implementation connected to the actual database."""
    
    def __init__(self, db_session):
        """
        Initialize with database session.
        
        Args:
            db_session: SQLAlchemy async session
        """
        super().__init__(db_session)
        self.db = db_session
    
    async def _get_spending_summary(self, user_id: str) -> Dict:
        """Get actual spending from database."""
        from sqlalchemy import select, func
        from datetime import date
        
        # This would be the real implementation
        # connecting to the Transaction model
        
        # For now, return mock data
        return await super()._get_spending_summary(user_id)


# =============================================================================
# INTEGRATION WITH BRAIN SERVICE
# =============================================================================

async def get_context_for_query(
    user_id: str,
    query: str,
    db_session=None,
) -> str:
    """
    Get formatted context for a user query.
    
    Helper function for brain service integration.
    """
    if db_session:
        rag = DatabaseRAG(db_session)
    else:
        rag = FinancialRAG()
    
    context = await rag.get_context(user_id, query)
    return rag.format_context(context)


# =============================================================================
# TESTING
# =============================================================================

async def test_rag():
    """Test the RAG system."""
    rag = FinancialRAG()
    
    # Test context retrieval
    context = await rag.get_context("test_user", "How much did I spend on food?")
    
    print("=" * 60)
    print("🔍 RAG Context Test")
    print("=" * 60)
    print("\nRaw context:")
    print(json.dumps(context, indent=2, default=str))
    print("\nFormatted context:")
    print(rag.format_context(context))


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_rag())
