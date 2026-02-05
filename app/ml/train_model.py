"""Train the global transaction categorization model."""

import os
import warnings
# Suppress numpy warnings on Windows
warnings.filterwarnings('ignore', category=RuntimeWarning)

from pathlib import Path
from typing import Tuple, Dict, Any
import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, classification_report
from sklearn.pipeline import Pipeline

from app.ml.training_data import prepare_training_data


def create_model_pipeline() -> Pipeline:
    """
    Create a scikit-learn pipeline for transaction categorization.
    
    Pipeline steps:
    1. TF-IDF Vectorization: Convert text to numerical features
    2. Multinomial Naive Bayes: Classify transactions
    
    Returns:
        Scikit-learn Pipeline
    """
    pipeline = Pipeline([
        ('tfidf', TfidfVectorizer(
            max_features=1000,  # Limit vocabulary size
            ngram_range=(1, 2),  # Use unigrams and bigrams
            min_df=2,  # Ignore terms that appear in fewer than 2 documents
            max_df=0.8,  # Ignore terms that appear in more than 80% of documents
        )),
        ('classifier', MultinomialNB(alpha=0.1))  # Laplace smoothing
    ])
    
    return pipeline


def train_model(
    descriptions: list[str],
    categories: list[str],
    test_size: float = 0.2,
    random_state: int = 42
) -> Tuple[Pipeline, Dict[str, Any]]:
    """
    Train the categorization model and evaluate its performance.
    
    Args:
        descriptions: List of transaction descriptions
        categories: List of corresponding categories
        test_size: Proportion of data to use for testing
        random_state: Random seed for reproducibility
        
    Returns:
        Tuple of (trained_model, metrics_dict)
    """
    # Split data into training and test sets
    X_train, X_test, y_train, y_test = train_test_split(
        descriptions,
        categories,
        test_size=test_size,
        random_state=random_state,
        stratify=categories  # Ensure balanced split across categories
    )
    
    print(f"Training set size: {len(X_train)}")
    print(f"Test set size: {len(X_test)}")
    print(f"Number of categories: {len(set(categories))}")
    
    # Create and train the model
    model = create_model_pipeline()
    print("\nTraining model...")
    model.fit(X_train, y_train)
    
    # Make predictions on test set
    print("Evaluating model...")
    y_pred = model.predict(X_test)
    
    # Calculate metrics
    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred, average='weighted', zero_division=0)
    recall = recall_score(y_test, y_pred, average='weighted', zero_division=0)
    f1 = f1_score(y_test, y_pred, average='weighted', zero_division=0)
    
    metrics = {
        'accuracy': accuracy,
        'precision': precision,
        'recall': recall,
        'f1_score': f1,
        'train_size': len(X_train),
        'test_size': len(X_test),
        'num_categories': len(set(categories))
    }
    
    # Print results
    print(f"\n{'='*60}")
    print("Model Performance Metrics")
    print(f"{'='*60}")
    print(f"Accuracy:  {accuracy:.4f} ({accuracy*100:.2f}%)")
    print(f"Precision: {precision:.4f}")
    print(f"Recall:    {recall:.4f}")
    print(f"F1 Score:  {f1:.4f}")
    print(f"{'='*60}")
    
    # Print detailed classification report
    print("\nDetailed Classification Report:")
    print(classification_report(y_test, y_pred, zero_division=0))
    
    # Check if accuracy meets target
    if accuracy >= 0.80:
        print("✓ Model meets target accuracy (>80%)")
    else:
        print("✗ Model does not meet target accuracy (>80%)")
        print(f"  Current: {accuracy*100:.2f}%, Target: 80.00%")
    
    return model, metrics


def save_model(model: Pipeline, metrics: Dict[str, Any], model_dir: str = "models") -> str:
    """
    Save the trained model and its metrics to disk.
    
    Args:
        model: Trained scikit-learn pipeline
        metrics: Dictionary of model performance metrics
        model_dir: Directory to save the model
        
    Returns:
        Path to the saved model file
    """
    # Create models directory if it doesn't exist
    Path(model_dir).mkdir(parents=True, exist_ok=True)
    
    # Save model
    model_path = os.path.join(model_dir, "global_categorization_model.pkl")
    joblib.dump(model, model_path)
    print(f"\nModel saved to: {model_path}")
    
    # Save metrics
    metrics_path = os.path.join(model_dir, "global_categorization_metrics.pkl")
    joblib.dump(metrics, metrics_path)
    print(f"Metrics saved to: {metrics_path}")
    
    return model_path


def load_model(model_path: str = "models/global_categorization_model.pkl") -> Pipeline:
    """
    Load a trained model from disk.
    
    Args:
        model_path: Path to the saved model file
        
    Returns:
        Loaded scikit-learn pipeline
    """
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model file not found: {model_path}")
    
    model = joblib.load(model_path)
    return model


def main() -> None:
    """Main function to train and save the global categorization model."""
    print("="*60)
    print("Training Global Transaction Categorization Model")
    print("="*60)
    
    # Prepare training data
    print("\nPreparing training data...")
    descriptions, categories = prepare_training_data()
    print(f"Loaded {len(descriptions)} training samples")
    
    # Train model
    model, metrics = train_model(descriptions, categories)
    
    # Save model
    model_path = save_model(model, metrics)
    
    # Test loading the model
    print("\nVerifying model can be loaded...")
    loaded_model = load_model(model_path)
    
    # Test prediction
    test_descriptions = [
        "whole foods market",
        "starbucks coffee",
        "shell gas station",
        "netflix subscription",
        "payroll deposit"
    ]
    
    print("\nTesting model predictions:")
    for desc in test_descriptions:
        prediction = loaded_model.predict([desc])[0]
        # Get probability scores
        proba = loaded_model.predict_proba([desc])[0]
        confidence = max(proba)
        print(f"  '{desc}' -> {prediction} (confidence: {confidence:.2f})")
    
    print("\n" + "="*60)
    print("Training complete!")
    print("="*60)


if __name__ == "__main__":
    main()
