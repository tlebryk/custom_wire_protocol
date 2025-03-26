import pytest
import sqlite3
import hashlib
import os
from users import (
    UserManager,
)  # Assuming the UserManager class is in user_manager.py


# Fixture to create a temporary SQLite database for each test
@pytest.fixture
def db_file(tmp_path):
    db_file = tmp_path / "test.db"
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    cursor.execute(
        """
        CREATE TABLE users (
            username TEXT PRIMARY KEY,
            password_hash TEXT
        )
    """
    )
    cursor.execute(
        """
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY,
            sender TEXT,
            content TEXT,
            FOREIGN KEY (sender) REFERENCES users (username)
        )
    """
    )
    conn.commit()
    conn.close()
    return str(db_file)


# Tests for register_user method
def test_register_user_success(db_file):
    um = UserManager(db_file)
    success, message = um.register_user("testuser", "password123")
    assert success, "Registration should succeed"
    assert message == "Registration successful. You can now log in."

    # Verify the user is in the database with the correct hash
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT password_hash FROM users WHERE username = ?", ("testuser",))
    row = cursor.fetchone()
    assert row is not None, "User should exist in the database"
    stored_hash = row[0]
    expected_hash = hashlib.sha256("password123".encode("utf-8")).hexdigest()
    assert stored_hash == expected_hash, "Password hash should match"
    conn.close()


def test_register_user_existing(db_file):
    um = UserManager(db_file)
    um.register_user("testuser", "password123")
    success, message = um.register_user("testuser", "anotherpassword")
    assert not success, "Registration should fail for existing username"
    assert message == "Username already exists."

    # Verify the original password hash remains unchanged
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT password_hash FROM users WHERE username = ?", ("testuser",))
    row = cursor.fetchone()
    assert row is not None, "User should still exist"
    stored_hash = row[0]
    expected_hash = hashlib.sha256("password123".encode("utf-8")).hexdigest()
    assert stored_hash == expected_hash, "Password hash should not change"
    conn.close()


# Tests for authenticate_user method
def test_authenticate_user_success(db_file):
    um = UserManager(db_file)
    um.register_user("testuser", "password123")
    assert um.authenticate_user(
        "testuser", "password123"
    ), "Authentication should succeed with correct credentials"


def test_authenticate_user_wrong_password(db_file):
    um = UserManager(db_file)
    um.register_user("testuser", "password123")
    assert not um.authenticate_user(
        "testuser", "wrongpassword"
    ), "Authentication should fail with incorrect password"


def test_authenticate_user_nonexistent(db_file):
    um = UserManager(db_file)
    assert not um.authenticate_user(
        "nonexistent", "password123"
    ), "Authentication should fail for non-existent user"


# Tests for delete_account method
def test_delete_account_success(db_file):
    um = UserManager(db_file)
    um.register_user("testuser", "password123")

    # Insert test messages
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO messages (sender, content) VALUES (?, ?)", ("testuser", "Hello")
    )
    cursor.execute(
        "INSERT INTO messages (sender, content) VALUES (?, ?)", ("testuser", "World")
    )
    conn.commit()
    conn.close()

    success = um.delete_account("testuser")
    assert success, "Account deletion should succeed"

    # Verify user and messages are deleted
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", ("testuser",))
    assert cursor.fetchone() is None, "User should be deleted"
    cursor.execute("SELECT * FROM messages WHERE sender = ?", ("testuser",))
    assert cursor.fetchone() is None, "User's messages should be deleted"
    conn.close()


def test_delete_account_messages(db_file):
    um = UserManager(db_file)
    um.register_user("user1", "password1")
    um.register_user("user2", "password2")

    # Insert test messages
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO messages (sender, content) VALUES (?, ?)", ("user1", "Msg1")
    )
    cursor.execute(
        "INSERT INTO messages (sender, content) VALUES (?, ?)", ("user2", "Msg2")
    )
    conn.commit()
    conn.close()

    success = um.delete_account("user1")
    assert success, "Account deletion should succeed"

    # Verify selective deletion
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", ("user1",))
    assert cursor.fetchone() is None, "User1 should be deleted"
    cursor.execute("SELECT * FROM users WHERE username = ?", ("user2",))
    assert cursor.fetchone() is not None, "User2 should remain"
    cursor.execute("SELECT * FROM messages WHERE sender = ?", ("user1",))
    assert cursor.fetchone() is None, "User1's messages should be deleted"
    cursor.execute("SELECT * FROM messages WHERE sender = ?", ("user2",))
    assert cursor.fetchone() is not None, "User2's messages should remain"
    conn.close()


def test_delete_account_nonexistent(db_file):
    um = UserManager(db_file)
    um.register_user("user1", "password1")
    success = um.delete_account("nonexistent")
    assert success, "Deletion should return True even for non-existent user"

    # Verify existing user remains unaffected
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", ("user1",))
    assert cursor.fetchone() is not None, "Existing user should remain"
    conn.close()
