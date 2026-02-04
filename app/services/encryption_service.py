"""Encryption service for securing sensitive data."""

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

from app.config import settings


class EncryptionService:
    """Service for encrypting and decrypting sensitive data using AES-256."""

    def __init__(self):
        """Initialize encryption service with key from settings."""
        self._cipher = self._create_cipher()

    def _create_cipher(self) -> Fernet:
        """Create Fernet cipher from encryption key in settings.
        
        Uses PBKDF2HMAC to derive a proper 32-byte key from the encryption_key setting.
        """
        # Use PBKDF2HMAC to derive a proper key from the encryption_key setting
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'ai_finance_platform_salt',  # Static salt for deterministic key
            iterations=100000
        )
        key = base64.urlsafe_b64encode(
            kdf.derive(settings.encryption_key.encode())
        )
        return Fernet(key)

    def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext string using AES-256.
        
        Args:
            plaintext: The string to encrypt
            
        Returns:
            Base64-encoded encrypted string
            
        Raises:
            ValueError: If plaintext is empty
        """
        if not plaintext:
            raise ValueError("Cannot encrypt empty string")
        
        encrypted_bytes = self._cipher.encrypt(plaintext.encode())
        return encrypted_bytes.decode()

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt ciphertext string.
        
        Args:
            ciphertext: The base64-encoded encrypted string
            
        Returns:
            Decrypted plaintext string
            
        Raises:
            ValueError: If ciphertext is empty or invalid
        """
        if not ciphertext:
            raise ValueError("Cannot decrypt empty string")
        
        try:
            decrypted_bytes = self._cipher.decrypt(ciphertext.encode())
            return decrypted_bytes.decode()
        except Exception as e:
            raise ValueError(f"Failed to decrypt data: {str(e)}")


# Global encryption service instance
encryption_service = EncryptionService()
