import pytest
import sqlite3
from datetime import datetime
import os
from database import (
    initialize_database,
    insert_message,
    get_recent_messages,
    get_undelivered_messages,
    mark_messages_delivered,
    get_unread_messages,
    mark_messages_as_read,
    get_user_info,
    set_n_unread_messages,
    delete_message,
    get_all_users_except,
    DB_FILE,
)


@pytest.fixture(autouse=True)
def setup_teardown():
    """Setup test database before each test and cleanup after."""
    # Setup
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
    initialize_database()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Create test users
    cursor.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        ("test_user1", "hash1"),
    )
    cursor.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        ("test_user2", "hash2"),
    )
    conn.commit()
    conn.close()

    yield

    # Teardown
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)


def test_insert_and_get_recent_messages():
    """Test inserting messages and retrieving recent messages."""
    # Insert test messages
    msg_id1 = insert_message("test_user1", "Hello!", "test_user2")
    msg_id2 = insert_message("test_user2", "Hi back!", "test_user1")

    # Mark messages as read to appear in recent messages
    mark_messages_as_read([msg_id1, msg_id2])

    # Get recent messages for test_user1
    messages = get_recent_messages("test_user1")

    assert len(messages) == 2
    assert messages[0][0] == "test_user1"  # sender
    assert messages[0][1] == "Hello!"  # content
    assert messages[0][2] == "test_user2"  # receiver
    assert messages[1][0] == "test_user2"  # sender
    assert messages[1][1] == "Hi back!"  # content
    assert messages[1][2] == "test_user1"  # receiver


def test_undelivered_messages():
    """Test getting and marking undelivered messages."""
    # Insert undelivered messages
    insert_message("test_user1", "Message 1", "test_user2")
    insert_message("test_user1", "Message 2", "test_user2")

    # Get undelivered messages
    undelivered = get_undelivered_messages("test_user2")
    assert len(undelivered) == 2
    assert undelivered[0][0] == "test_user1"  # sender
    assert undelivered[0][1] == "Message 1"  # content

    # Mark messages as delivered
    mark_messages_delivered("test_user2")

    # Verify no undelivered messages remain
    undelivered = get_undelivered_messages("test_user2")
    assert len(undelivered) == 0


def test_unread_messages():
    """Test getting and marking unread messages."""
    # Insert messages
    msg_id1 = insert_message("test_user1", "Unread 1", "test_user2")
    msg_id2 = insert_message("test_user1", "Unread 2", "test_user2")

    # Get unread messages
    unread = get_unread_messages("test_user2")
    assert len(unread) == 2
    assert unread[0][1] == "test_user1"  # sender
    assert unread[0][2] == "Unread 1"  # content

    # Mark one message as read
    mark_messages_as_read([msg_id1])

    # Verify only one unread message remains
    unread = get_unread_messages("test_user2")
    assert len(unread) == 1
    assert unread[0][2] == "Unread 2"  # content


def test_user_info():
    """Test getting and updating user information."""
    # Get initial user info
    user_info = get_user_info("test_user1")
    assert user_info is not None
    assert user_info[0] == "test_user1"
    assert user_info[1] == 0  # initial unread messages

    # Update unread messages
    success = set_n_unread_messages("test_user1", 5)
    assert success is True

    # Verify update
    user_info = get_user_info("test_user1")
    assert user_info[1] == 5


def test_delete_message():
    """Test message deletion."""
    # Insert a message
    msg_id = insert_message("test_user1", "Delete me", "test_user2")

    # Delete the message
    success = delete_message(msg_id)
    assert success is True

    # Verify message is deleted (should not appear in recent messages)
    mark_messages_as_read(
        [msg_id]
    )  # Mark as read to make it visible in recent messages
    messages = get_recent_messages("test_user2")
    assert len(messages) == 0


def test_get_all_users_except():
    """Test getting all users except specified user."""
    users = get_all_users_except("test_user1")
    assert len(users) == 1
    assert "test_user2" in users
    assert "test_user1" not in users


def test_message_timestamp_format():
    """Test that message timestamps are in correct ISO format."""
    msg_id = insert_message("test_user1", "Time test", "test_user2")
    mark_messages_as_read([msg_id])
    messages = get_recent_messages("test_user1")

    # Verify timestamp format
    timestamp = messages[0][3]
    try:
        datetime.fromisoformat(timestamp.rstrip("Z"))
        assert timestamp.endswith("Z")  # Check UTC marker
    except ValueError:
        pytest.fail("Timestamp is not in valid ISO format")


def test_message_ordering():
    """Test that messages are returned in correct order."""
    # Insert messages in sequence
    msg_ids = []
    for i in range(3):
        msg_id = insert_message("test_user1", f"Message {i}", "test_user2")
        msg_ids.append(msg_id)

    mark_messages_as_read(msg_ids)
    messages = get_recent_messages("test_user2")

    # Verify messages are in chronological order
    assert len(messages) == 3
    for i, message in enumerate(messages):
        assert message[1] == f"Message {i}"


def test_non_existent_user():
    """Test handling of non-existent users."""
    user_info = get_user_info("non_existent_user")
    assert user_info is None

    users = get_all_users_except("non_existent_user")
    assert len(users) == 2  # should still return all users
