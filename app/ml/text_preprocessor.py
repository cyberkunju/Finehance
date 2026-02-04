"""
Text preprocessing module for transaction categorization.
This module must be importable when loading the trained model.
"""
import re


def preprocess_transaction(text: str) -> str:
    """
    Preprocess a transaction description for ML model input.
    
    Args:
        text: Raw transaction description
        
    Returns:
        Cleaned and normalized text
    """
    if not isinstance(text, str):
        return ""
    
    # Lowercase
    text = text.lower().strip()
    
    # Remove store numbers like #1234
    text = re.sub(r'#\d+', ' ', text)
    
    # Remove long numbers (reference numbers, etc)
    text = re.sub(r'\d{4,}', ' ', text)
    
    # Remove reference numbers
    text = re.sub(r'ref\d+', ' ', text, flags=re.IGNORECASE)
    
    # Remove special characters but keep spaces
    text = re.sub(r'[^\w\s]', ' ', text)
    
    # Normalize whitespace
    text = ' '.join(text.split())
    
    # Expand common abbreviations
    abbreviations = {
        'mcd': 'mcdonalds',
        'wb': 'walmart',
        'amzn': 'amazon',
        'aapl': 'apple',
        'msft': 'microsoft',
        'goog': 'google',
        'fb': 'facebook',
        'nflx': 'netflix',
        'sbux': 'starbucks',
    }
    
    words = text.split()
    words = [abbreviations.get(w, w) for w in words]
    text = ' '.join(words)
    
    return text
