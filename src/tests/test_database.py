import pytest
import sqlite3
from datetime import datetime
import os
from time import sleep
from database import Database  # Use the new class-based API


@pytest.fixture(autouse=True)
def setup_teardown(tmp_path):
    """Setup test database before each test and cleanup after."""
    # Create a temporary database file.
    db_file = tmp_path / "test_chat_app.db"
    # Instantiate a Database with the temporary file.
    db = Database(str(db_file))

    # Create test users.
    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()
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

    yield db
    # Teardown: remove the temporary database file.
    if os.path.exists(str(db_file)):
        os.remove(str(db_file))


def test_insert_and_get_recent_messages(setup_teardown):
    """Test inserting messages and retrieving recent messages."""
    db = setup_teardown
    # Insert test messages.
    msg_id1 = db.insert_message("test_user1", "Hello!", "test_user2")
    msg_id2 = db.insert_message("test_user2", "Hi back!", "test_user1")
    # Mark messages as read to appear in recent messages.
    db.mark_messages_as_read([msg_id1, msg_id2])
    # Get recent messages for test_user1.
    messages = db.get_recent_messages("test_user1")
    assert len(messages) == 2
    # Verify sender, content, receiver ordering.
    # Note: get_recent_messages returns rows ordered from oldest to newest.
    assert messages[0][0] == "test_user1"  # sender of first message
    assert messages[0][1] == "Hello!"  # content of first message
    assert messages[0][2] == "test_user2"  # receiver of first message
    assert messages[1][0] == "test_user2"  # sender of second message
    assert messages[1][1] == "Hi back!"  # content of second message
    assert messages[1][2] == "test_user1"  # receiver of second message


def test_undelivered_messages(setup_teardown):
    """Test getting and marking undelivered messages."""
    db = setup_teardown
    # Insert undelivered messages.
    db.insert_message("test_user1", "Message 1", "test_user2")
    db.insert_message("test_user1", "Message 2", "test_user2")
    # Get undelivered messages.
    undelivered = db.get_undelivered_messages("test_user2")
    assert len(undelivered) == 2
    assert undelivered[0][0] == "test_user1"  # sender
    assert undelivered[0][1] == "Message 1"  # content
    # Mark messages as delivered.
    db.mark_messages_delivered("test_user2")
    # Verify no undelivered messages remain.
    undelivered = db.get_undelivered_messages("test_user2")
    assert len(undelivered) == 0
    sleep(0.5)


def test_unread_messages(setup_teardown):
    """Test getting and marking unread messages."""
    db = setup_teardown
    # Insert messages.
    msg_id1 = db.insert_message("test_user1", "Unread 1", "test_user2")
    msg_id2 = db.insert_message("test_user1", "Unread 2", "test_user2")
    # Get unread messages.
    unread = db.get_unread_messages("test_user2")
    assert len(unread) == 2
    assert unread[0][1] == "test_user1"  # sender
    assert unread[0][2] == "Unread 1"  # content
    # Mark one message as read.
    db.mark_messages_as_read([msg_id1])
    # Verify only one unread message remains.
    unread_after = db.get_unread_messages("test_user2")
    assert len(unread_after) == 1
    assert unread_after[0][2] == "Unread 2"  # content
    sleep(0.5)


def test_user_info(setup_teardown):
    """Test getting and updating user information."""
    db = setup_teardown
    # Get initial user info.
    user_info = db.get_user_info("test_user1")
    assert user_info is not None
    assert user_info[0] == "test_user1"
    assert user_info[1] == 0  # initial unread messages
    # Update unread messages.
    success = db.set_n_unread_messages("test_user1", 5)
    assert success is True
    # Verify update.
    user_info = db.get_user_info("test_user1")
    assert user_info[1] == 5
    sleep(0.5)


def test_delete_message(setup_teardown):
    """Test message deletion."""
    db = setup_teardown
    # Insert a message.
    msg_id = db.insert_message("test_user1", "Delete me", "test_user2")
    # Delete the message.
    success = db.delete_message(msg_id)
    assert success is True
    # Mark as read to ensure it's visible in recent messages.
    db.mark_messages_as_read([msg_id])
    messages = db.get_recent_messages("test_user2")
    assert len(messages) == 0
    sleep(0.5)


def test_get_all_users_except(setup_teardown):
    """Test getting all users except specified user."""
    db = setup_teardown
    users = db.get_all_users_except("test_user1")
    assert len(users) == 1
    assert "test_user2" in users
    assert "test_user1" not in users
    sleep(0.5)


def test_message_timestamp_format(setup_teardown):
    """Test that message timestamps are in correct ISO format."""
    db = setup_teardown
    msg_id = db.insert_message("test_user1", "Time test", "test_user2")
    db.mark_messages_as_read([msg_id])
    messages = db.get_recent_messages("test_user1")
    timestamp = messages[0][3]
    try:
        # Remove trailing "Z" before parsing.
        datetime.fromisoformat(timestamp.rstrip("Z"))
        assert timestamp.endswith("Z")  # Check for UTC marker.
    except ValueError:
        pytest.fail("Timestamp is not in valid ISO format")
    sleep(0.5)


def test_message_ordering(setup_teardown):
    """Test that messages are returned in correct order."""
    db = setup_teardown
    msg_ids = []
    for i in range(3):
        msg_id = db.insert_message("test_user1", f"Message {i}", "test_user2")
        msg_ids.append(msg_id)
    db.mark_messages_as_read(msg_ids)
    messages = db.get_recent_messages("test_user2")
    assert len(messages) == 3
    for i, message in enumerate(messages):
        assert message[1] == f"Message {i}"
    sleep(0.5)


def test_non_existent_user(setup_teardown):
    """Test handling of non-existent users."""
    db = setup_teardown
    user_info = db.get_user_info("non_existent_user")
    assert user_info is None
    users = db.get_all_users_except("non_existent_user")
    # Since we inserted two test users in setup, we expect both to be returned.
    assert len(users) == 2
    sleep(0.5)
