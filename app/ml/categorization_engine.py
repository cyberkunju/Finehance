"""Categorization Engine for automatic transaction classification."""

import os
import json
import asyncio
from typing import Optional, Tuple, List
from decimal import Decimal
from dataclasses import dataclass
from datetime import datetime
import joblib
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.metrics import accuracy_score, precision_recall_fscore_support

from app.ml.text_preprocessor import preprocess_transaction as preprocess_text
from app.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class CategoryPrediction:
    """Result of transaction categorization."""

    category: str
    confidence: float
    model_type: str  # "GLOBAL" or "USER_SPECIFIC"


class CategorizationEngine:
    """
    Engine for automatic transaction categorization.

    Uses a pre-trained global model for cold-start users and can learn
    from user corrections to build personalized models.
    """

    def __init__(self, model_dir: str = "models"):
        """
        Initialize the categorization engine.

        Args:
            model_dir: Directory containing trained models
        """
        self.model_dir = model_dir
        self.global_model: Optional[Pipeline] = None
        self.user_models: dict[str, Pipeline] = {}
        self.user_corrections: dict[
            str, List[Tuple[str, str]]
        ] = {}  # user_id -> [(description, category)]
        self.min_corrections_for_training = 50  # Minimum corrections before training user model

        # Load global model on initialization
        self._load_global_model()

        # Ensure model directory exists
        os.makedirs(self.model_dir, exist_ok=True)

    def _load_global_model(self) -> None:
        """Load the pre-trained global categorization model."""
        model_path = os.path.join(self.model_dir, "global_categorization_model.pkl")

        if not os.path.exists(model_path):
            logger.warning("Global categorization model not found", model_path=model_path)
            return

        try:
            self.global_model = joblib.load(model_path)
            logger.info("Global categorization model loaded successfully")
        except Exception as e:
            logger.error("Failed to load global categorization model", error=str(e))

    async def _load_user_model(self, user_id: str) -> Optional[Pipeline]:
        """
        Load a user-specific categorization model.

        Args:
            user_id: User ID

        Returns:
            User-specific model if exists, None otherwise
        """
        # Check cache first
        if user_id in self.user_models:
            return self.user_models[user_id]

        # Try to load from disk
        model_path = os.path.join(self.model_dir, f"user_{user_id}_categorization_model.pkl")

        if not os.path.exists(model_path):
            return None

        try:
            loop = asyncio.get_running_loop()
            model = await loop.run_in_executor(None, joblib.load, model_path)
            self.user_models[user_id] = model
            logger.info("User-specific categorization model loaded", user_id=user_id)
            return model
        except Exception as e:
            logger.error(
                "Failed to load user-specific categorization model", user_id=user_id, error=str(e)
            )
            return None

    async def should_use_global_model(self, user_id: Optional[str]) -> bool:
        """
        Determine if global model should be used for this user.

        Uses global model if:
        - No user_id provided
        - User has no personalized model
        - User has insufficient transaction history

        Args:
            user_id: User ID

        Returns:
            True if global model should be used
        """
        if not user_id:
            return True

        # Check if user has a personalized model
        user_model = await self._load_user_model(user_id)
        if not user_model:
            return True

        return False

    async def categorize(
        self,
        description: str,
        amount: Optional[Decimal] = None,
        user_id: Optional[str] = None,
    ) -> CategoryPrediction:
        """
        Predict category for a transaction description.

        Args:
            description: Transaction description text
            amount: Transaction amount (optional, for future enhancements)
            user_id: User ID (optional, for personalized models)

        Returns:
            CategoryPrediction with category, confidence score, and model type

        Raises:
            ValueError: If global model is not loaded and no user model exists
        """
        # Preprocess description
        processed_desc = preprocess_text(description)

        # Determine which model to use
        use_global = await self.should_use_global_model(user_id)

        if use_global:
            if not self.global_model:
                raise ValueError("Global categorization model not loaded")

            model = self.global_model
            model_type = "GLOBAL"
        else:
            model = await self._load_user_model(user_id)
            if not model:
                # Fallback to global model
                if not self.global_model:
                    raise ValueError("No categorization model available")
                model = self.global_model
                model_type = "GLOBAL"
            else:
                model_type = "USER_SPECIFIC"

        # Make prediction
        try:
            category = model.predict([processed_desc])[0]

            # Get confidence score (probability of predicted class)
            probabilities = model.predict_proba([processed_desc])[0]
            confidence = float(max(probabilities))

            logger.debug(
                "Transaction categorized",
                description=description,
                category=category,
                confidence=confidence,
                model_type=model_type,
                user_id=user_id,
            )

            return CategoryPrediction(
                category=category, confidence=confidence, model_type=model_type
            )

        except Exception as e:
            logger.error("Categorization failed", description=description, error=str(e))
            # Return "Uncategorized" as fallback
            return CategoryPrediction(
                category="Other Expenses", confidence=0.0, model_type=model_type
            )

    def categorize_batch(
        self,
        descriptions: List[str],
        amounts: Optional[List[Optional[Decimal]]] = None,
        user_id: Optional[str] = None,
    ) -> List[CategoryPrediction]:
        """
        Predict categories for a batch of transaction descriptions.

        Args:
            descriptions: List of transaction description texts
            amounts: List of transaction amounts (optional)
            user_id: User ID (optional, for personalized models)

        Returns:
            List of CategoryPrediction objects

        Raises:
            ValueError: If global model is not loaded and no user model exists
        """
        if not descriptions:
            return []

        # Determine which model to use (once for the whole batch)
        use_global = self._should_use_global_model_sync(user_id)

        if use_global:
            if not self.global_model:
                raise ValueError("Global categorization model not loaded")

            model = self.global_model
            model_type = "GLOBAL"
        else:
            model = self._load_user_model_sync(user_id)
            if not model:
                # Fallback to global model
                if not self.global_model:
                    raise ValueError("No categorization model available")
                model = self.global_model
                model_type = "GLOBAL"
            else:
                model_type = "USER_SPECIFIC"

        # Preprocess all descriptions
        processed_descs = [preprocess_text(desc) for desc in descriptions]

        try:
            import numpy as np
            # Vectorized prediction
            categories = model.predict(processed_descs)

            # Vectorized probabilities
            # predict_proba returns array of shape (n_samples, n_classes)
            # we want the max probability for each sample
            all_probabilities = model.predict_proba(processed_descs)
            confidences = np.max(all_probabilities, axis=1)

            results = []
            for i, (category, confidence) in enumerate(zip(categories, confidences)):
                # Cast confidence to float (it might be numpy float)
                results.append(
                    CategoryPrediction(
                        category=category,
                        confidence=float(confidence),
                        model_type=model_type,
                    )
                )

            logger.info(
                "Batch categorization completed",
                batch_size=len(descriptions),
                model_type=model_type,
                user_id=user_id,
            )

            return results

        except Exception as e:
            logger.error(
                "Batch categorization failed, falling back to sequential",
                error=str(e),
                batch_size=len(descriptions),
            )
            # Fallback to sequential processing for robustness
            results = []
            for i, desc in enumerate(descriptions):
                amt = amounts[i] if amounts and i < len(amounts) else None
                try:
                    # Use sync categorize method in batch context
                    results.append(self._categorize_sync(desc, amt, user_id))
                except Exception:
                    results.append(
                        CategoryPrediction(
                            category="Other Expenses",
                            confidence=0.0,
                            model_type=model_type,
                        )
                    )
            return results

    def _should_use_global_model_sync(self, user_id: Optional[str]) -> bool:
        """Synchronous version of should_use_global_model for batch processing."""
        if not user_id:
            return True
        model_path = os.path.join(self.model_dir, f"user_{user_id}_categorization_model.pkl")
        return not os.path.exists(model_path)

    def _load_user_model_sync(self, user_id: str) -> Optional[Pipeline]:
        """Synchronous version of _load_user_model for batch processing."""
        if user_id in self.user_models:
            return self.user_models[user_id]
        model_path = os.path.join(self.model_dir, f"user_{user_id}_categorization_model.pkl")
        if not os.path.exists(model_path):
            return None
        try:
            model = joblib.load(model_path)
            self.user_models[user_id] = model
            return model
        except Exception:
            return None

    def _categorize_sync(
        self,
        description: str,
        amount: Optional[Decimal] = None,
        user_id: Optional[str] = None,
    ) -> CategoryPrediction:
        """Synchronous version of categorize for batch processing fallback."""
        processed_desc = preprocess_text(description)
        use_global = self._should_use_global_model_sync(user_id)

        if use_global:
            if not self.global_model:
                raise ValueError("Global categorization model not loaded")
            model = self.global_model
            model_type = "GLOBAL"
        else:
            model = self._load_user_model_sync(user_id)
            if not model:
                if not self.global_model:
                    raise ValueError("No categorization model available")
                model = self.global_model
                model_type = "GLOBAL"
            else:
                model_type = "USER_SPECIFIC"

        try:
            category = model.predict([processed_desc])[0]
            probabilities = model.predict_proba([processed_desc])[0]
            confidence = float(max(probabilities))
            return CategoryPrediction(
                category=category, confidence=confidence, model_type=model_type
            )
        except Exception:
            return CategoryPrediction(
                category="Other Expenses", confidence=0.0, model_type=model_type
            )

    def learn_from_correction(self, user_id: str, description: str, correct_category: str) -> bool:
        """
        Update user-specific model with a correction.

        This method stores the correction and triggers model retraining
        when sufficient corrections have been accumulated.

        Args:
            user_id: User ID
            description: Transaction description
            correct_category: Correct category provided by user

        Returns:
            True if model was retrained, False otherwise
        """
        logger.info(
            "User correction recorded",
            user_id=user_id,
            description=description,
            correct_category=correct_category,
        )

        # Load existing corrections for this user
        corrections = self._load_user_corrections(user_id)

        # Add new correction
        corrections.append((description, correct_category))

        # Save corrections to disk
        self._save_user_corrections(user_id, corrections)

        # Check if we have enough corrections to train/retrain model
        if len(corrections) >= self.min_corrections_for_training:
            logger.info(
                "Sufficient corrections accumulated, training user model",
                user_id=user_id,
                correction_count=len(corrections),
            )

            # Train user-specific model
            success = self._train_user_model(user_id, corrections)

            if success:
                logger.info("User-specific model trained successfully", user_id=user_id)
                return True
            else:
                logger.warning("Failed to train user-specific model", user_id=user_id)
                return False

        logger.debug(
            "Correction stored, waiting for more data",
            user_id=user_id,
            correction_count=len(corrections),
            required=self.min_corrections_for_training,
        )

        return False

    def _load_user_corrections(self, user_id: str) -> List[Tuple[str, str]]:
        """
        Load user corrections from disk.

        Args:
            user_id: User ID

        Returns:
            List of (description, category) tuples
        """
        corrections_path = os.path.join(self.model_dir, f"user_{user_id}_corrections.json")

        if not os.path.exists(corrections_path):
            return []

        try:
            with open(corrections_path, "r") as f:
                data = json.load(f)
                return [(item["description"], item["category"]) for item in data]
        except Exception as e:
            logger.error("Failed to load user corrections", user_id=user_id, error=str(e))
            return []

    def _save_user_corrections(self, user_id: str, corrections: List[Tuple[str, str]]) -> None:
        """
        Save user corrections to disk.

        Args:
            user_id: User ID
            corrections: List of (description, category) tuples
        """
        corrections_path = os.path.join(self.model_dir, f"user_{user_id}_corrections.json")

        try:
            data = [{"description": desc, "category": cat} for desc, cat in corrections]

            with open(corrections_path, "w") as f:
                json.dump(data, f, indent=2)

            logger.debug("User corrections saved", user_id=user_id, count=len(corrections))
        except Exception as e:
            logger.error("Failed to save user corrections", user_id=user_id, error=str(e))

    def _train_user_model(self, user_id: str, corrections: List[Tuple[str, str]]) -> bool:
        """
        Train a user-specific categorization model.

        Args:
            user_id: User ID
            corrections: List of (description, category) tuples

        Returns:
            True if training succeeded, False otherwise
        """
        try:
            # Prepare training data
            descriptions = [preprocess_text(desc) for desc, _ in corrections]
            categories = [cat for _, cat in corrections]

            # Check if we have enough unique categories
            unique_categories = set(categories)
            if len(unique_categories) < 2:
                logger.warning(
                    "Insufficient category diversity for training",
                    user_id=user_id,
                    unique_categories=len(unique_categories),
                )
                return False

            # Create and train model pipeline
            # Use same architecture as global model for consistency
            model = Pipeline(
                [
                    (
                        "tfidf",
                        TfidfVectorizer(
                            max_features=1000,
                            ngram_range=(1, 2),
                            min_df=1,  # Lower threshold for user models
                            max_df=0.95,
                        ),
                    ),
                    ("classifier", MultinomialNB(alpha=0.1)),
                ]
            )

            model.fit(descriptions, categories)

            # Calculate metrics
            predictions = model.predict(descriptions)
            accuracy = accuracy_score(categories, predictions)
            precision, recall, f1, _ = precision_recall_fscore_support(
                categories, predictions, average="weighted", zero_division=0
            )

            metrics = {
                "accuracy": float(accuracy),
                "precision": float(precision),
                "recall": float(recall),
                "f1_score": float(f1),
                "training_samples": len(corrections),
                "unique_categories": len(unique_categories),
                "trained_at": datetime.utcnow().isoformat(),
            }

            # Save model
            model_path = os.path.join(self.model_dir, f"user_{user_id}_categorization_model.pkl")
            joblib.dump(model, model_path)

            # Save metrics
            metrics_path = os.path.join(
                self.model_dir, f"user_{user_id}_categorization_metrics.pkl"
            )
            joblib.dump(metrics, metrics_path)

            # Update cache
            self.user_models[user_id] = model

            logger.info(
                "User model trained successfully",
                user_id=user_id,
                accuracy=accuracy,
                training_samples=len(corrections),
                unique_categories=len(unique_categories),
            )

            return True

        except Exception as e:
            logger.error("Failed to train user model", user_id=user_id, error=str(e))
            return False

    async def get_model_accuracy(self, user_id: str) -> float:
        """
        Get current accuracy for user's personalized model.

        Args:
            user_id: User ID

        Returns:
            Model accuracy (0.0 to 1.0), or 0.0 if no user model exists
        """
        # Try to load metrics
        metrics_path = os.path.join(self.model_dir, f"user_{user_id}_categorization_metrics.pkl")

        if not os.path.exists(metrics_path):
            # No user model, return global model accuracy
            global_metrics_path = os.path.join(self.model_dir, "global_categorization_metrics.pkl")
            if os.path.exists(global_metrics_path):
                try:
                    loop = asyncio.get_running_loop()
                    metrics = await loop.run_in_executor(None, joblib.load, global_metrics_path)
                    return metrics.get("accuracy", 0.0)
                except Exception as e:
                    logger.error("Failed to load global metrics", error=str(e))
                    return 0.0
            else:
                logger.warning("Global metrics file not found", path=global_metrics_path)
            return 0.0

        try:
            loop = asyncio.get_running_loop()
            metrics = await loop.run_in_executor(None, joblib.load, metrics_path)
            return metrics.get("accuracy", 0.0)
        except Exception as e:
            logger.error("Failed to load model metrics", user_id=user_id, error=str(e))
            return 0.0

    def get_correction_count(self, user_id: str) -> int:
        """
        Get the number of corrections stored for a user.

        Args:
            user_id: User ID

        Returns:
            Number of corrections
        """
        corrections = self._load_user_corrections(user_id)
        return len(corrections)

    def has_user_model(self, user_id: str) -> bool:
        """
        Check if a user has a personalized model.

        Args:
            user_id: User ID

        Returns:
            True if user has a personalized model
        """
        model_path = os.path.join(self.model_dir, f"user_{user_id}_categorization_model.pkl")
        return os.path.exists(model_path)
