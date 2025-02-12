# conftest.py

import pytest
from unittest.mock import MagicMock, patch

# tests/conftest.py
import pytest
import threading
import time
import server  # Assuming server.py is in the root directory
import logging


@pytest.fixture(scope="session")
def websocket_server():
    """
    Fixture to start the WebSocket server in a separate thread.
    """
    # Configure logging to show only critical errors during tests
    logging.getLogger().setLevel(logging.CRITICAL)

    server_thread = threading.Thread(target=server.main, daemon=True)
    server_thread.start()

    # Wait for the server to start
    time.sleep(1)  # Adjust if necessary based on server startup time

    yield

    # Teardown logic (if any) can be added here
    # Since the server runs in a daemon thread, it will exit when tests finish


@pytest.fixture
def mock_conn():
    """
    Fixture to create a mock connection object.
    """
    return MagicMock()


@pytest.fixture
def mock_send_ws_frame():
    """
    Fixture to mock the send_ws_frame function from handlers.
    """
    with patch("handlers.send_ws_frame") as mock_send:
        yield mock_send


@pytest.fixture
def mock_read_ws_frame():
    """
    Fixture to mock the read_ws_frame function from handlers.
    """
    with patch("handlers.read_ws_frame") as mock_read:
        yield mock_read


@pytest.fixture
def mock_perform_handshake():
    """
    Fixture to mock the perform_handshake function from handlers.
    """
    with patch("handlers.perform_handshake") as mock_handshake:
        yield mock_handshake


@pytest.fixture
def mock_register_user():
    """
    Fixture to mock the register_user function from handlers.
    """
    with patch("handlers.register_user") as mock_register:
        yield mock_register


@pytest.fixture
def mock_authenticate_user():
    """
    Fixture to mock the authenticate_user function from handlers.
    """
    with patch("handlers.authenticate_user") as mock_authenticate:
        yield mock_authenticate


@pytest.fixture
def mock_delete_account():
    """
    Fixture to mock the delete_account function from handlers.
    """
    with patch("handlers.delete_account") as mock_delete:
        yield mock_delete


@pytest.fixture
def mock_insert_message():
    """
    Fixture to mock the insert_message function from handlers.
    """
    with patch("handlers.insert_message") as mock_insert:
        yield mock_insert


@pytest.fixture
def mock_get_recent_messages():
    """
    Fixture to mock the get_recent_messages function from handlers.
    """
    with patch("handlers.get_recent_messages") as mock_recent:
        yield mock_recent


@pytest.fixture
def mock_get_undelivered_messages():
    """
    Fixture to mock the get_undelivered_messages function from handlers.
    """
    with patch("handlers.get_undelivered_messages") as mock_undelivered:
        yield mock_undelivered


@pytest.fixture
def mock_mark_messages_delivered():
    """
    Fixture to mock the mark_messages_delivered function from handlers.
    """
    with patch("handlers.mark_messages_delivered") as mock_mark_delivered:
        yield mock_mark_delivered


@pytest.fixture
def mock_get_unread_messages():
    """
    Fixture to mock the get_unread_messages function from handlers.
    """
    with patch("handlers.get_unread_messages") as mock_unread:
        yield mock_unread


@pytest.fixture
def mock_mark_messages_as_read():
    """
    Fixture to mock the mark_messages_as_read function from handlers.
    """
    with patch("handlers.mark_messages_as_read") as mock_mark_read:
        yield mock_mark_read


@pytest.fixture
def mock_online_users():
    """
    Fixture to mock the online_users dictionary from handlers.
    """
    with patch("handlers.online_users", {}) as mock_users:
        yield mock_users
