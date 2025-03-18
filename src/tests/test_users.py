import pytest
import sqlite3
import os
from users import UserManager

# Use an in-memory SQLite database for testing
TEST_DB_FILE = ":memory:"


@pytest.fixture
def user_manager():
    """Fixture to create a fresh UserManager instance with an in-memory database."""
    return UserManager(db_file=TEST_DB_FILE)


def test_hash_password(user_manager):
    """Test password hashing functionality."""
    password = "test123"
    hashed = user_manager._hash_password(
        password
    )  # Using private method directly for test purposes

    assert isinstance(hashed, str)
    assert len(hashed) == 64  # SHA-256 produces 64 character hex string

    # Test consistency
    assert user_manager._hash_password(password) == user_manager._hash_password(
        password
    )

    # Test different passwords produce different hashes
    assert user_manager._hash_password("test123") != user_manager._hash_password(
        "test124"
    )

    # Test empty string
    assert len(user_manager._hash_password("")) == 64


def test_register_user_empty_credentials(user_manager):
    """Test registration with empty credentials."""
    success, message = user_manager.register_user("", "")
    assert success is False
    assert "failed" in message.lower()


def test_password_hash_security(user_manager):
    """Test security aspects of password hashing."""
    password = "test123"
    hashed = user_manager._hash_password(password)

    # Test that similar passwords produce different hashes
    similar_passwords = ["test1234", "Test123", "test 123", "test123 "]
    for similar_pwd in similar_passwords:
        assert user_manager._hash_password(similar_pwd) != hashed


def test_register_and_authenticate_user(user_manager):
    """Test registering a user and authenticating them."""
    username = "test_user"
    password = "securepassword"

    # Register the user
    success, message = user_manager.register_user(username, password)
    assert success is True
    assert "successful" in message.lower()

    # Authenticate with correct password
    assert user_manager.authenticate_user(username, password) is True

    # Authenticate with incorrect password
    assert user_manager.authenticate_user(username, "wrongpassword") is False


def test_register_duplicate_user(user_manager):
    """Test that registering a duplicate username fails."""
    username = "duplicate_user"
    password = "password123"

    # First registration should succeed
    success, message = user_manager.register_user(username, password)
    assert success is True

    # Second registration should fail
    success, message = user_manager.register_user(username, password)
    assert success is False
    assert "already exists" in message.lower()


def test_delete_nonexistent_account(user_manager):
    """Test deleting a non-existent account."""
    success = user_manager.delete_account("nonexistent_user")
    assert success is False


def test_register_and_delete_user(user_manager):
    """Test registering and then deleting a user."""
    username = "delete_me"
    password = "mypassword"

    # Register the user
    success, _ = user_manager.register_user(username, password)
    assert success is True

    # Authenticate to ensure user exists
    assert user_manager.authenticate_user(username, password) is True

    # Delete the user
    success = user_manager.delete_account(username)
    assert success is True

    # Ensure authentication fails after deletion
    assert user_manager.authenticate_user(username, password) is False
