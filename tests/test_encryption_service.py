"""Tests for encryption service."""

import pytest
from app.services.encryption_service import EncryptionService, encryption_service


class TestEncryptionService:
    """Test suite for EncryptionService."""

    def test_encrypt_decrypt_roundtrip(self):
        """Test that encryption and decryption work correctly."""
        service = EncryptionService()
        plaintext = "my-secret-access-token-12345"

        encrypted = service.encrypt(plaintext)
        decrypted = service.decrypt(encrypted)

        assert decrypted == plaintext
        assert encrypted != plaintext

    def test_encrypt_produces_different_output(self):
        """Test that encryption produces different output each time (due to IV)."""
        service = EncryptionService()
        plaintext = "my-secret-token"

        encrypted1 = service.encrypt(plaintext)
        encrypted2 = service.encrypt(plaintext)

        # Fernet includes timestamp and IV, so outputs differ
        assert encrypted1 != encrypted2
        # But both decrypt to same value
        assert service.decrypt(encrypted1) == plaintext
        assert service.decrypt(encrypted2) == plaintext

    def test_encrypt_empty_string_raises_error(self):
        """Test that encrypting empty string raises ValueError."""
        service = EncryptionService()

        with pytest.raises(ValueError, match="Cannot encrypt empty string"):
            service.encrypt("")

    def test_decrypt_empty_string_raises_error(self):
        """Test that decrypting empty string raises ValueError."""
        service = EncryptionService()

        with pytest.raises(ValueError, match="Cannot decrypt empty string"):
            service.decrypt("")

    def test_decrypt_invalid_ciphertext_raises_error(self):
        """Test that decrypting invalid ciphertext raises ValueError."""
        service = EncryptionService()

        with pytest.raises(ValueError, match="Failed to decrypt data"):
            service.decrypt("invalid-ciphertext")

    def test_encrypt_long_string(self):
        """Test encryption of long strings."""
        service = EncryptionService()
        plaintext = "a" * 10000  # 10KB string

        encrypted = service.encrypt(plaintext)
        decrypted = service.decrypt(encrypted)

        assert decrypted == plaintext

    def test_encrypt_special_characters(self):
        """Test encryption of strings with special characters."""
        service = EncryptionService()
        plaintext = "token!@#$%^&*()_+-=[]{}|;':\",./<>?`~"

        encrypted = service.encrypt(plaintext)
        decrypted = service.decrypt(encrypted)

        assert decrypted == plaintext

    def test_encrypt_unicode_characters(self):
        """Test encryption of strings with unicode characters."""
        service = EncryptionService()
        plaintext = "token-with-émojis-🔐🔑🛡️"

        encrypted = service.encrypt(plaintext)
        decrypted = service.decrypt(encrypted)

        assert decrypted == plaintext

    def test_global_encryption_service_instance(self):
        """Test that global encryption service instance works."""
        plaintext = "test-token-123"

        encrypted = encryption_service.encrypt(plaintext)
        decrypted = encryption_service.decrypt(encrypted)

        assert decrypted == plaintext

    def test_encryption_is_deterministic_with_same_key(self):
        """Test that two service instances with same key can decrypt each other's data."""
        service1 = EncryptionService()
        service2 = EncryptionService()

        plaintext = "shared-secret"
        encrypted = service1.encrypt(plaintext)
        decrypted = service2.decrypt(encrypted)

        assert decrypted == plaintext
