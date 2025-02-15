import pytest
import sqlite3
import os
from users import (
    hash_password,
    register_user,
    authenticate_user,
    delete_account,
    DB_FILE,
)


def test_hash_password():
    """Test password hashing functionality."""
    # Test basic hashing
    password = "test123"
    hashed = hash_password(password)
    assert isinstance(hashed, str)
    assert len(hashed) == 64  # SHA-256 produces 64 character hex string

    # Test consistency
    assert hash_password(password) == hash_password(password)

    # Test different passwords produce different hashes
    assert hash_password("test123") != hash_password("test124")

    # Test empty string
    assert len(hash_password("")) == 64


def test_register_user_empty_credentials():
    """Test registration with empty credentials."""
    success, message = register_user("", "")
    assert success is False
    assert "failed" in message.lower()


def test_password_hash_security():
    """Test security aspects of password hashing."""
    password = "test123"
    hashed = hash_password(password)

    # Test that similar passwords produce different hashes
    similar_passwords = ["test1234", "Test123", "test 123", "test123 "]

    for similar_pwd in similar_passwords:
        assert hash_password(similar_pwd) != hashed


def test_delete_nonexistent_account():
    """Test deleting a non-existent account."""
    success = delete_account("nonexistent")
    assert success is False
